"""Backward-compatibility shim.

.. deprecated:: 2.0
    Import from :mod:`voltsdk.io.msgpack` and
    :mod:`voltsdk.integrations.glb` instead.
"""

from __future__ import annotations

import warnings

warnings.warn(
    'voltsdk.utils is deprecated. '
    'Use voltsdk.io.msgpack for msgpack_as_df and '
    'voltsdk.integrations.glb for view_glb.',
    DeprecationWarning,
    stacklevel=2,
)

from .io.msgpack import get_nested_value, merged_chunked_value, msgpack_as_df
from .integrations.glb import view_glb

__all__ = ['msgpack_as_df', 'view_glb', 'get_nested_value', 'merged_chunked_value']
