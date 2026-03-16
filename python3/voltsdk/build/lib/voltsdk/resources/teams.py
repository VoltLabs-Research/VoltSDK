"""Team resource.

A :class:`Team` is resolved lazily from the secret key via
``GET /teams/secret-keys/me`` and exposes basic team metadata.
"""

from __future__ import annotations

from .base import BaseResource


class Team(BaseResource):
    """Represents a Volt team associated with the current secret key."""

    @property
    def name(self) -> str:
        """Human-readable team name."""
        # The /teams/secret-keys/me endpoint returns the team object
        # nested under ``team`` or at top-level depending on the shape.
        team_data = self._data.get('teamData', self._data)
        if isinstance(team_data, dict):
            return team_data.get('name', '')
        return ''

    @property
    def team_id(self) -> str:
        """The team ID string (convenience alias for ``self.id``)."""
        return self._data.get('team', '') or self.id

    def __repr__(self) -> str:
        name = self.name
        tid = self.team_id
        if name:
            return f'<Team name={name!r} id={tid}>'
        return f'<Team id={tid}>'
