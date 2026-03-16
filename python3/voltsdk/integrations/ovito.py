"""OVITO integration helpers.

Provides :func:`create_pipeline` and :func:`frame_to_data` for
converting Volt trajectory data into OVITO objects for advanced
structural analysis.

Requires the ``ovito`` package (``pip install "voltsdk[ovito]"``).
"""

from __future__ import annotations

import gzip
import os
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voltsdk.resources.trajectories import Trajectory
    from voltsdk.resources.frames import Frame


def _ensure_ovito():
    """Import and return the ovito.io module, raising a clear error if missing."""
    try:
        from ovito.io import import_file
        return import_file
    except ImportError as exc:
        raise ImportError(
            'ovito is required for this feature. '
            'Install with: pip install "voltsdk[ovito]"'
        ) from exc


def _decompress_gz(gz_path: str) -> str:
    """Decompress a ``.gz`` file in-place and return the decompressed path."""
    if not gz_path.endswith('.gz'):
        return gz_path
    decompressed = gz_path[:-3]
    with gzip.open(gz_path, 'rb') as f_in:
        with open(decompressed, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return decompressed


def create_pipeline(
    trajectory: Trajectory,
    timesteps: list[int] | None = None,
    dest: str | None = None,
    analysis_id: str = 'default',
):
    """Create an OVITO Pipeline from a Volt trajectory.

    Downloads dump files for the requested timesteps and creates
    an OVITO ``FileSource`` pipeline.

    Parameters
    ----------
    trajectory:
        The Volt trajectory resource.
    timesteps:
        Specific timesteps to download.  Default: all frames.
    dest:
        Directory for downloaded dump files.
        Default: ``./volt_dumps/{trajectory.id}/``.
    analysis_id:
        Analysis context for frame data.  Default ``"default"``.

    Returns
    -------
    ovito.Pipeline
    """
    import_file = _ensure_ovito()

    frames = list(trajectory.frames)
    if timesteps is not None:
        ts_set = set(timesteps)
        frames = [f for f in frames if f.timestep in ts_set]

    if not frames:
        raise ValueError('No frames found for the specified timesteps.')

    dest = dest or f'./volt_dumps/{trajectory.id}/'
    os.makedirs(dest, exist_ok=True)

    dump_files: list[str] = []
    for frame in frames:
        dump_path = frame.download_dump(dest=dest)
        dump_path = _decompress_gz(dump_path)
        dump_files.append(dump_path)

    if len(dump_files) == 1:
        pipeline = import_file(dump_files[0])
    else:
        # Try importing first file; OVITO may auto-discover the series
        pipeline = import_file(dump_files[0], sort_particles=True)
        # If OVITO didn't find all frames, explicitly pass the full list
        if pipeline.source.num_frames < len(dump_files):
            pipeline = import_file(dump_files)

    return pipeline


def frame_to_data(frame: Frame):
    """Convert a single Volt Frame to an OVITO DataCollection.

    Downloads the dump file, decompresses if needed, and computes
    the OVITO pipeline to produce a ``DataCollection``.

    Parameters
    ----------
    frame:
        The Volt frame resource.

    Returns
    -------
    ovito.data.DataCollection
    """
    import_file = _ensure_ovito()

    dump_path = frame.download_dump()
    dump_path = _decompress_gz(dump_path)

    pipeline = import_file(dump_path)
    return pipeline.compute()
