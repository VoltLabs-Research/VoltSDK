"""VoltSDK — Python SDK for the Volt scientific computing platform.

Quick start::

    from voltsdk import VoltClient

    client = VoltClient.from_env()          # inside Volt notebooks
    client = VoltClient(secret_key="vsk_…") # explicit key

    for traj in client.trajectories:
        print(traj.name, traj.frame_count)
"""

from .client import VoltClient
from .exceptions import (
    VoltError,
    VoltAPIError,
    VoltAuthenticationError,
    VoltConnectionError,
    VoltNotFoundError,
    VoltPermissionError,
    VoltTimeoutError,
)

# Backward-compatible re-exports from the old utils.py
from .io.msgpack import msgpack_as_df
from .integrations.glb import view_glb

__all__ = [
    # Core
    'VoltClient',
    # Exceptions
    'VoltError',
    'VoltAPIError',
    'VoltAuthenticationError',
    'VoltConnectionError',
    'VoltNotFoundError',
    'VoltPermissionError',
    'VoltTimeoutError',
    # Utilities (backward compat)
    'msgpack_as_df',
    'view_glb',
]

__version__ = '2.0.0'
