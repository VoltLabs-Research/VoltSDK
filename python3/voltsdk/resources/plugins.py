"""Plugin resource and collection.

A :class:`Plugin` represents an analysis plugin registered in the Volt
platform (e.g. *Common Neighbor Analysis*, *Dislocation Analysis*).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseResource, BaseCollection

if TYPE_CHECKING:
    from voltsdk.http import HttpTransport


class Plugin(BaseResource):
    """Represents a Volt analysis plugin."""

    @property
    def name(self) -> str:
        return self._get('name', '')

    @property
    def display_name(self) -> str:
        return self._get('displayName', '') or self.name

    @property
    def description(self) -> str:
        return self._get('description', '')

    @property
    def version(self) -> str:
        return self._get('version', '')

    def __repr__(self) -> str:
        return f'<Plugin name={self.display_name!r} id={self.id}>'


class PluginCollection(BaseCollection['Plugin']):
    """Collection of available analysis plugins."""

    def __init__(
        self,
        client: HttpTransport,
        params: dict | None = None,
        page_size: int = 100,
    ) -> None:
        team_id = client.team_id
        super().__init__(
            client,
            path=f'/plugins/{team_id}/',
            resource_cls=Plugin,
            params=params,
            page_size=page_size,
        )

    def get(self, plugin_id: str) -> Plugin:
        """Fetch a single plugin by ID."""
        team_id = self._client.team_id
        data = self._client.get(f'/plugins/{team_id}/{plugin_id}')
        return Plugin(self._client, data)
