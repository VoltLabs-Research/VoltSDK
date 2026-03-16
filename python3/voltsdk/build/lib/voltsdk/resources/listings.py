"""Listing resources with native DataFrame support.

:class:`ListingCollection` provides paginated access to plugin listing
rows (the tabular results produced by analysis plugins).  It auto-
paginates and exposes ``.to_dataframe()``, ``.to_csv()``, and
``.plot()`` for quick scientific exploration.

:class:`AnalysisListingProxy` and :class:`TrajectoryListingProxy` are
thin wrappers that aggregate listings at the analysis or trajectory
level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    from voltsdk.http import HttpTransport


class ListingCollection:
    """Paginated access to plugin listing rows with DataFrame conversion.

    Parameters
    ----------
    client:
        HTTP transport.
    path:
        API path for the listing endpoint.
    params:
        Extra query-string parameters (e.g. filters).
    """

    def __init__(
        self,
        client: HttpTransport,
        path: str,
        params: dict | None = None,
    ) -> None:
        self._client = client
        self._path = path
        self._params = params or {}
        self._meta: dict | None = None

    # ------------------------------------------------------------------
    # Internal fetch
    # ------------------------------------------------------------------

    def _fetch(
        self,
        page: int = 1,
        limit: int = 200,
        sort_asc: bool = True,
    ) -> dict:
        params = {
            **self._params,
            'page': page,
            'limit': limit,
            'sortAsc': sort_asc,
        }
        response = self._client.get(self._path, params=params)
        if isinstance(response, dict):
            self._meta = response.get('_meta', self._meta)
        return response

    # ------------------------------------------------------------------
    # Column introspection
    # ------------------------------------------------------------------

    @property
    def columns(self) -> list[str]:
        """Column labels from the plugin schema (lazy-loaded)."""
        if self._meta is None:
            self._fetch(page=1, limit=1)
        return [c['label'] for c in (self._meta or {}).get('columns', [])]

    # ------------------------------------------------------------------
    # DataFrame conversion
    # ------------------------------------------------------------------

    def to_dataframe(
        self,
        sort_asc: bool = True,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch **all** listing rows and return as a pandas DataFrame.

        Parameters
        ----------
        sort_asc:
            Sort by timestep ascending (default ``True``).
        columns:
            Select only these columns.  Default: all.

        Returns
        -------
        pd.DataFrame
        """
        import pandas as _pd

        all_rows: list[dict] = []
        page = 1
        while True:
            response = self._fetch(page=page, limit=200, sort_asc=sort_asc)
            rows = response.get('data', []) if isinstance(response, dict) else []
            if not rows:
                break
            all_rows.extend(rows)
            total_pages = response.get('totalPages', 1) if isinstance(response, dict) else 1
            if page >= total_pages:
                break
            page += 1

        df = _pd.DataFrame(all_rows)
        if columns and not df.empty:
            available = [c for c in columns if c in df.columns]
            df = df[available]
        return df

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_csv(self, path: str | None = None) -> str:
        """Export listings to CSV via the server API.

        Parameters
        ----------
        path:
            Local file path.  If ``None`` the server picks the name.

        Returns
        -------
        str
            Path to the downloaded CSV file.
        """
        return self._client.download_stream(
            self._path + '/export',
            fallback_name='listings.csv',
            params={**self._params, 'format': 'csv'},
        )

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def plot(self, x: str = 'timestep', y=None, **kwargs):
        """Quick plot of listing data.

        Parameters
        ----------
        x:
            Column for x-axis (default ``"timestep"``).
        y:
            Column(s) for y-axis.  ``None`` → all numeric columns.
        **kwargs:
            Forwarded to ``DataFrame.plot()``.

        Returns
        -------
        matplotlib.axes.Axes
        """
        from voltsdk.integrations.plotting import plot_listing
        return plot_listing(self, x=x, y=y, **kwargs)

    def __repr__(self) -> str:
        return f'<ListingCollection path={self._path!r}>'


# ------------------------------------------------------------------
# Proxy classes that aggregate listings at higher levels
# ------------------------------------------------------------------

class AnalysisListingProxy:
    """Aggregate listing access for a single analysis.

    Delegates to :class:`ListingCollection` using the analysis's listing
    endpoint.
    """

    def __init__(self, client: HttpTransport, analysis) -> None:
        self._client = client
        self._analysis = analysis

    def _collection(self) -> ListingCollection:
        team_id = self._client.team_id
        return ListingCollection(
            self._client,
            path=f'/plugins/{team_id}/listings/analyses/{self._analysis.id}',
        )

    @property
    def columns(self) -> list[str]:
        return self._collection().columns

    def to_dataframe(self, **kwargs) -> pd.DataFrame:
        return self._collection().to_dataframe(**kwargs)

    def to_csv(self, path: str | None = None) -> str:
        return self._collection().to_csv(path)

    def plot(self, x: str = 'timestep', y=None, **kwargs):
        return self._collection().plot(x=x, y=y, **kwargs)

    def __repr__(self) -> str:
        return f'<AnalysisListingProxy analysis={self._analysis.id}>'


class TrajectoryListingProxy:
    """Aggregate listing access across **all** analyses of a trajectory.

    Iterates over every completed analysis, fetches their listings, and
    concatenates them into a single DataFrame.
    """

    def __init__(self, client: HttpTransport, trajectory) -> None:
        self._client = client
        self._trajectory = trajectory

    def to_dataframe(self, **kwargs) -> pd.DataFrame:
        """Concatenate listings from all completed analyses."""
        import pandas as _pd

        dfs: list[_pd.DataFrame] = []
        for analysis in self._trajectory.analyses:
            if analysis.status != 'completed':
                continue
            try:
                df = analysis.listings.to_dataframe(**kwargs)
                if not df.empty:
                    df['_analysis'] = analysis.plugin_name
                    df['_analysis_id'] = analysis.id
                    dfs.append(df)
            except Exception:
                continue

        if not dfs:
            return _pd.DataFrame()
        return _pd.concat(dfs, ignore_index=True)

    def plot(self, columns, x: str = 'timestep', **kwargs):
        """Plot listing data from all analyses of the trajectory."""
        from voltsdk.integrations.plotting import plot_trajectory_listings
        return plot_trajectory_listings(self._trajectory, columns, x=x, **kwargs)

    def __repr__(self) -> str:
        return f'<TrajectoryListingProxy trajectory={self._trajectory.id}>'
