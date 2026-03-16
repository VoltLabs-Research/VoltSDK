"""Low-level HTTP transport with retries, auth, and streaming downloads.

:class:`HttpTransport` is the single networking gateway used by every
resource class.  It handles:

* Bearer-token authentication via ``Authorization`` header.
* Automatic retries with exponential back-off on transient 5xx errors.
* Consistent response unwrapping  (``{status, data}`` envelope).
* Streaming file downloads with progress logging.
* Recursive zip extraction.
"""

from __future__ import annotations

import logging
import os
import zipfile
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    VoltAPIError,
    VoltAuthenticationError,
    VoltConnectionError,
    VoltNotFoundError,
    VoltPermissionError,
    VoltTimeoutError,
)

logger = logging.getLogger('voltsdk')


class HttpTransport:
    """Low-level HTTP transport with retries, auth, and streaming."""

    def __init__(
        self,
        base_url: str,
        secret_key: str,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._team_id: str | None = None

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {secret_key}',
            'Accept': 'application/json',
        })

        # Retry with exponential back-off on transient failures
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=['GET'],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    # ------------------------------------------------------------------
    # Team context (lazy)
    # ------------------------------------------------------------------

    @property
    def team_id(self) -> str:
        """Return the team ID for the current secret key (lazy-loaded)."""
        if self._team_id is None:
            data = self.get('/teams/secret-keys/me')
            self._team_id = data.get('team')
        return self._team_id  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Core HTTP verbs
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Send a GET request and return the unwrapped ``data`` payload."""
        return self._request('GET', path, params=params)

    def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """Send a POST request and return the unwrapped ``data`` payload."""
        return self._request('POST', path, json=json, params=params)

    # ------------------------------------------------------------------
    # Internal request handling
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        kwargs.setdefault('timeout', self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.ConnectionError as exc:
            raise VoltConnectionError(f'Cannot connect to {url}') from exc
        except requests.Timeout as exc:
            raise VoltTimeoutError(f'Request timed out: {url}') from exc

        # Map HTTP status codes to specific exceptions
        if response.status_code == 401:
            raise VoltAuthenticationError('Invalid or expired secret key')
        if response.status_code == 403:
            raise VoltPermissionError('Insufficient permissions')
        if response.status_code == 404:
            raise VoltNotFoundError(f'Resource not found: {path}')
        if response.status_code >= 400:
            try:
                msg = response.json().get('message', response.text)
            except Exception:
                msg = response.text
            raise VoltAPIError(response.status_code, msg, url)

        payload = response.json()
        if payload.get('status') != 'success':
            raise VoltAPIError(
                response.status_code,
                payload.get('message', 'Unknown error'),
                url,
            )
        return payload.get('data', {})

    # ------------------------------------------------------------------
    # Streaming downloads
    # ------------------------------------------------------------------

    def download_stream(
        self,
        path: str,
        fallback_name: str,
        dest: str = '.',
        params: dict[str, Any] | None = None,
    ) -> str:
        """Download a file via streaming.

        Parameters
        ----------
        path:
            API path (appended to ``base_url``).
        fallback_name:
            Filename used when the server does not provide one via
            ``Content-Disposition``.
        dest:
            Directory to write the file into.
        params:
            Optional query-string parameters.

        Returns
        -------
        str
            Absolute path to the downloaded file.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        os.makedirs(dest, exist_ok=True)

        with self.session.get(
            url, stream=True, timeout=self.timeout, params=params,
        ) as response:
            if response.status_code >= 400:
                raise VoltAPIError(response.status_code, 'Download failed', url)

            # Resolve filename from Content-Disposition header
            cd = response.headers.get('Content-Disposition', '')
            if 'filename=' in cd:
                filename = cd.split('filename=')[-1].strip().strip('"').strip("'")
                filename = os.path.basename(filename) if filename else fallback_name
            else:
                filename = fallback_name

            file_path = os.path.join(dest, filename)
            total = int(response.headers.get('Content-Length', 0) or 0)
            downloaded = 0

            with open(file_path, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
                        downloaded += len(chunk)

            logger.info('Downloaded %s (%d bytes)', filename, downloaded)

        return file_path

    # ------------------------------------------------------------------
    # Zip extraction
    # ------------------------------------------------------------------

    @staticmethod
    def unzip_recursive(zip_path: str) -> str:
        """Extract a zip file recursively (handles nested zips).

        The top-level zip is **preserved**; only nested zips inside the
        extracted tree are removed after extraction.

        Returns the path to the extraction directory.
        """
        if not zip_path.lower().endswith('.zip'):
            return zip_path

        extract_dir = zip_path[:-4]
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # Recursively extract nested zips
        while True:
            nested: list[str] = []
            for root, _, files in os.walk(extract_dir):
                for fname in files:
                    if fname.lower().endswith('.zip'):
                        nested.append(os.path.join(root, fname))
            if not nested:
                break
            for nz in nested:
                sub_dir = nz[:-4]
                os.makedirs(sub_dir, exist_ok=True)
                with zipfile.ZipFile(nz, 'r') as zf:
                    zf.extractall(sub_dir)
                os.remove(nz)  # Only remove nested zips

        return extract_dir
