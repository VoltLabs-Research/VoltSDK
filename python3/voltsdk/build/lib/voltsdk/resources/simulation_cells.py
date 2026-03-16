"""Simulation cell resource.

A :class:`SimulationCell` wraps the simulation box geometry returned by
``GET /simulation-cells/{teamId}/trajectories/{trajectoryId}``.
"""

from __future__ import annotations

from .base import BaseResource


class SimulationCell(BaseResource):
    """Simulation cell / box geometry for a trajectory."""

    @property
    def bounds(self) -> dict:
        """Box bounds dictionary as returned by the server."""
        return self._data.get('bounds', self._data)

    @property
    def cell_vectors(self) -> list[list[float]]:
        """Cell vectors (3x3), if available."""
        return self._data.get('cellVectors', [])

    @property
    def periodic(self) -> list[bool]:
        """Periodic boundary flags ``[x, y, z]``."""
        return self._data.get('periodic', [True, True, True])

    def __repr__(self) -> str:
        return f'<SimulationCell id={self.id}>'
