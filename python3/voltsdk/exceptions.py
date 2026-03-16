"""Custom exception hierarchy for the VoltSDK.

All SDK-specific exceptions inherit from :class:`VoltError`, making it
easy to catch any Volt-related failure with a single ``except VoltError``
clause while still allowing fine-grained handling of authentication,
permission, or network issues.
"""

from __future__ import annotations


class VoltError(Exception):
    """Base exception for all VoltSDK errors."""


class VoltAuthenticationError(VoltError):
    """Invalid or expired secret key."""


class VoltPermissionError(VoltError):
    """Insufficient permissions for the requested operation."""


class VoltNotFoundError(VoltError):
    """Requested resource does not exist."""


class VoltAPIError(VoltError):
    """Server returned an error response.

    Attributes
    ----------
    status_code : int
        HTTP status code from the server.
    url : str
        The request URL that produced the error.
    """

    def __init__(self, status_code: int, message: str, url: str = '') -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f'{status_code}: {message} ({url})')


class VoltConnectionError(VoltError):
    """Network connectivity issue."""


class VoltTimeoutError(VoltError):
    """Request timed out."""
