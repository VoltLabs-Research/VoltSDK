"""Download management utilities.

This module re-exports the download and extraction helpers from
:class:`~voltsdk.http.HttpTransport` for standalone use, and adds
convenience functions for common download patterns.
"""

from __future__ import annotations

import os
from pathlib import Path


def ensure_directory(path: str) -> str:
    """Create *path* if it doesn't exist and return it."""
    os.makedirs(path, exist_ok=True)
    return path


def find_files(directory: str, extension: str) -> list[str]:
    """Recursively find all files with the given *extension* under *directory*.

    Parameters
    ----------
    directory:
        Root directory to search.
    extension:
        File extension to match (e.g. ``".msgpack"``, ``".glb"``).
        Case-insensitive.

    Returns
    -------
    list[str]
        Sorted list of absolute file paths.
    """
    ext = extension.lower()
    results: list[str] = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith(ext):
                results.append(os.path.join(root, fname))
    results.sort()
    return results


def find_msgpack_files(directory: str) -> list[str]:
    """Find all ``.msgpack`` files under *directory*."""
    return find_files(directory, '.msgpack')


def find_glb_files(directory: str) -> list[str]:
    """Find all ``.glb`` files under *directory*."""
    return find_files(directory, '.glb')
