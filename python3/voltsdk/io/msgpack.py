"""MessagePack parsing utilities.

Provides :func:`msgpack_as_df` for loading Volt analysis result files
(``*.msgpack``) into pandas DataFrames, with support for chunked
streaming and nested key extraction.

These functions were originally in ``voltsdk/utils.py`` and are
preserved with the same signatures for backward compatibility.
"""

from __future__ import annotations

import os
from typing import Any

import msgpack
import pandas as pd


def get_nested_value(data: Any, path: str | None) -> Any:
    """Traverse *data* using a dot-separated *path*.

    >>> get_nested_value({'a': {'b': 42}}, 'a.b')
    42
    """
    if not path:
        return data

    current = data
    for key in path.split('.'):
        if not isinstance(current, dict):
            return None
        if key not in current:
            return None
        current = current[key]
    return current


def merged_chunked_value(target: Any, incoming: Any) -> Any:
    """Merge two chunks produced by iterative msgpack unpacking.

    Lists are concatenated, dicts are recursively merged, and scalars
    are overwritten.
    """
    if incoming is None:
        return target
    if target is None:
        return incoming

    if isinstance(target, list) and isinstance(incoming, list):
        target.extend(incoming)
        return target

    if isinstance(target, dict) and isinstance(incoming, dict):
        for key, incoming_value in incoming.items():
            target_value = target.get(key)
            if isinstance(target_value, list) and isinstance(incoming_value, list):
                target_value.extend(incoming_value)
            elif isinstance(target_value, dict) and isinstance(incoming_value, dict):
                target[key] = merged_chunked_value(target_value, incoming_value)
            else:
                target[key] = incoming_value
        return target

    return incoming


def _is_columnar_dict(value: Any) -> bool:
    """Return ``True`` if *value* looks like ``{col: [values], ...}``."""
    if not isinstance(value, dict) or not value:
        return False
    lengths: list[int] = []
    for item in value.values():
        if not isinstance(item, list):
            return False
        lengths.append(len(item))
    return len(set(lengths)) == 1


def msgpack_as_df(
    file_path: str,
    iterable_key: str | None = None,
) -> pd.DataFrame:
    """Load a Volt msgpack file into a pandas DataFrame.

    Parameters
    ----------
    file_path:
        Path to the ``.msgpack`` file.
    iterable_key:
        Optional dot-separated path to extract from each chunk before
        merging (e.g. ``"main_listing"``).

    Returns
    -------
    pd.DataFrame
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f'File not found: {file_path}')

    data: Any = None
    with open(file_path, 'rb') as fh:
        unpacker = msgpack.Unpacker(fh, raw=False)
        for message in unpacker:
            chunk = get_nested_value(message, iterable_key)
            data = merged_chunked_value(data, chunk)

    if data is None:
        return pd.DataFrame()

    if isinstance(data, list) or _is_columnar_dict(data):
        return pd.DataFrame(data)

    if isinstance(data, dict):
        return pd.DataFrame([data])

    return pd.DataFrame([{'value': data}])
