"""VoltClient — the main entry point for the VoltSDK.

Usage::

    from voltsdk import VoltClient

    # Inside a Volt Jupyter notebook (zero-config):
    client = VoltClient.from_env()

    # Explicit secret key:
    client = VoltClient(secret_key="vsk_xxxxx")

    # Fully explicit (external Jupyter, e.g. Google Colab):
    client = VoltClient(
        secret_key="vsk_xxxxx",
        base_url="https://server.voltcloud.dev/api",
    )

No network calls are made during construction.  The first network call
happens lazily when a resource property is accessed.
"""

from __future__ import annotations

import os
import warnings
from typing import Any

from .http import HttpTransport
from .resources.teams import Team
from .resources.trajectories import Trajectory, TrajectoryCollection
from .resources.analyses import AnalysisCollection
from .resources.plugins import PluginCollection


class VoltClient:
    """Client for the Volt scientific computing platform.

    Parameters
    ----------
    secret_key:
        Team secret key (prefix ``vsk_``).  If not provided, reads from
        the ``VOLT_SECRET_KEY`` environment variable.
    base_url:
        Volt API endpoint.  If not provided, reads from
        ``VOLT_BASE_URL``, or falls back to auto-detection from the
        Jupyter proxy configuration.

    No network calls are made during construction.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._secret_key = secret_key or os.environ.get('VOLT_SECRET_KEY')
        self._base_url = (
            base_url
            or os.environ.get('VOLT_BASE_URL')
            or self._detect_base_url()
        )

        if not self._secret_key:
            raise ValueError(
                'secret_key is required. '
                'Provide it directly or set VOLT_SECRET_KEY.'
            )
        if not self._base_url:
            raise ValueError(
                'base_url is required. '
                'Provide it directly or set VOLT_BASE_URL.'
            )

        self._http = HttpTransport(
            base_url=self._base_url,
            secret_key=self._secret_key,
        )

        # Lazy-loaded team context
        self._team: Team | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> VoltClient:
        """Create a client using environment variables.

        Reads ``VOLT_SECRET_KEY`` and ``VOLT_BASE_URL`` from the
        environment.  This is the recommended way to authenticate inside
        Volt notebooks.
        """
        return cls()

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_base_url() -> str | None:
        """Auto-detect base URL inside Volt Jupyter containers."""
        for var in ('VOLT_SERVER_URL', 'JUPYTERHUB_API_URL'):
            url = os.environ.get(var)
            if url:
                return url.rstrip('/') + '/api'
        return None

    # ------------------------------------------------------------------
    # Team context (lazy)
    # ------------------------------------------------------------------

    @property
    def team(self) -> Team:
        """The team associated with the current secret key (lazy-loaded)."""
        if self._team is None:
            data = self._http.get('/teams/secret-keys/me')
            self._team = Team(self._http, data)
        return self._team

    # ------------------------------------------------------------------
    # Resource collections
    # ------------------------------------------------------------------

    @property
    def trajectories(self) -> TrajectoryCollection:
        """Lazy, paginated collection of trajectories."""
        return TrajectoryCollection(self._http)

    @property
    def analyses(self) -> AnalysisCollection:
        """Lazy, paginated collection of analyses (team-wide)."""
        team_id = self._http.team_id
        return AnalysisCollection(
            self._http,
            path=f'/analyses/{team_id}/',
        )

    @property
    def plugins(self) -> PluginCollection:
        """Lazy, paginated collection of available analysis plugins."""
        return PluginCollection(self._http)

    # ------------------------------------------------------------------
    # Deprecated legacy API (backward compatibility)
    # ------------------------------------------------------------------

    def list_analyses(
        self,
        trajectory_id: str,
        page: int = 1,
        limit: int = 1000,
    ) -> list[dict]:
        """.. deprecated:: 2.0
            Use ``client.trajectories.get(id).analyses`` instead.
        """
        warnings.warn(
            'list_analyses() is deprecated. '
            'Use client.trajectories.get(id).analyses instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        response = self._http.get(
            f'/analyses/{self._http.team_id}/trajectory/{trajectory_id}',
            params={'page': page, 'limit': limit},
        )
        data = response.get('data', response) if isinstance(response, dict) else response
        return data if isinstance(data, list) else []

    def find_analysis_by_id(self, analysis_id: str) -> dict:
        """.. deprecated:: 2.0
            Use ``client.trajectories.get(tid).analyses`` and filter.
        """
        warnings.warn(
            'find_analysis_by_id() is deprecated.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self._http.get(
            f'/analyses/{self._http.team_id}/{analysis_id}',
        )

    def list_analysis_results(
        self,
        analysis_id: str,
        page: int = 1,
        limit: int = 1000,
    ) -> list[dict]:
        """.. deprecated:: 2.0
            Use ``analysis.listings.to_dataframe()`` instead.
        """
        warnings.warn(
            'list_analysis_results() is deprecated. '
            'Use analysis.listings.to_dataframe() instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        response = self._http.get(
            f'/plugins/{self._http.team_id}/listings/analyses/{analysis_id}',
            params={'page': page, 'limit': limit},
        )
        data = response.get('data', response) if isinstance(response, dict) else response
        return data if isinstance(data, list) else []

    def download_analysis_artifacts(
        self,
        analysis_id: str,
        unzip: bool = True,
    ) -> str:
        """.. deprecated:: 2.0
            Use ``analysis.download_artifacts()`` instead.
        """
        warnings.warn(
            'download_analysis_artifacts() is deprecated. '
            'Use analysis.download_artifacts() instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        zip_path = self._http.download_stream(
            f'/plugins/{self._http.team_id}/exposures/analyses/{analysis_id}/export',
            fallback_name=f'analysis-{analysis_id}-artifacts.zip',
        )
        if unzip:
            return self._http.unzip_recursive(zip_path)
        return zip_path

    def download_plugin_results_file(
        self,
        analysis_id: str,
        unzip: bool = True,
    ) -> str:
        """.. deprecated:: 2.0
            Alias for :meth:`download_analysis_artifacts`.
        """
        warnings.warn(
            'download_plugin_results_file() is deprecated. '
            'Use analysis.download_artifacts() instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self.download_analysis_artifacts(analysis_id, unzip=unzip)

    def download_frame_glb(
        self,
        analysis_id: str,
        timestep: int,
    ) -> str:
        """.. deprecated:: 2.0
            Use ``frame.download_glb(analysis_id=...)`` instead.
        """
        warnings.warn(
            'download_frame_glb() is deprecated. '
            'Use frame.download_glb(analysis_id=...) instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        trajectory_id = self._resolve_trajectory_id(analysis_id)
        return self._http.download_stream(
            f'/trajectories/{self._http.team_id}/{trajectory_id}/glb/{timestep}/{analysis_id}',
            fallback_name=f'frame-{analysis_id}-{timestep}.glb',
        )

    def download_plugin_exported_glb(
        self,
        analysis_id: str,
        exposure_id: str,
        timestep: int,
    ) -> str:
        """.. deprecated:: 2.0
            Use ``exposure.download_glb(timestep=...)`` instead.
        """
        warnings.warn(
            'download_plugin_exported_glb() is deprecated. '
            'Use exposure.download_glb(timestep=...) instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        trajectory_id = self._resolve_trajectory_id(analysis_id)
        return self._http.download_stream(
            f'/plugins/{self._http.team_id}/exposures/glb/{trajectory_id}/{analysis_id}/{exposure_id}/{timestep}',
            fallback_name=f'plugin-glb-{analysis_id}-{exposure_id}-{timestep}.glb',
        )

    # ------------------------------------------------------------------
    # Internal helpers for deprecated methods
    # ------------------------------------------------------------------

    def _resolve_trajectory_id(self, analysis_id: str) -> str:
        """Fetch analysis to get its trajectory ID."""
        analysis = self._http.get(
            f'/analyses/{self._http.team_id}/{analysis_id}',
        )
        trajectory_id = analysis.get('trajectory')
        if not trajectory_id:
            raise RuntimeError('Analysis trajectory not found')
        return trajectory_id

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f'<VoltClient base_url={self._base_url!r}>'
