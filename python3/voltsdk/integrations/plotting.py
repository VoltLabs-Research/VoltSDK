"""Matplotlib convenience wrappers for Volt listing data.

All functions accept :class:`~voltsdk.resources.listings.ListingCollection`
or trajectory/analysis objects and produce publication-ready plots with
sensible defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from voltsdk.resources.listings import ListingCollection


def plot_listing(
    listing_collection: ListingCollection,
    x: str = 'timestep',
    y=None,
    ax=None,
    **kwargs,
):
    """Plot listing data using matplotlib.

    Parameters
    ----------
    listing_collection:
        The listing data source.
    x:
        Column for x-axis.  Default ``"timestep"``.
    y:
        Column(s) for y-axis.  ``None`` plots all numeric columns.
    ax:
        Axes to plot on.  Creates a new figure if ``None``.
    **kwargs:
        Passed to ``DataFrame.plot()``.

    Returns
    -------
    matplotlib.axes.Axes or list[matplotlib.axes.Axes] or None
    """
    df = listing_collection.to_dataframe()

    if df.empty:
        return None

    if y is None:
        exclude = {
            '_id', 'analysisId', 'trajectoryId',
            'exposureId', 'trajectoryName',
        }
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        y = [c for c in numeric_cols if c not in exclude and c != x]

    if isinstance(y, str):
        y = [y]

    if not y:
        return None

    if ax is None:
        n_cols = len(y)
        if n_cols == 1:
            fig, ax = plt.subplots(figsize=(10, 5))
            df.plot(x=x, y=y[0], ax=ax, **kwargs)
            ax.set_ylabel(y[0])
            return ax
        else:
            fig, axes = plt.subplots(1, n_cols, figsize=(5 * n_cols, 4))
            if n_cols == 1:
                axes = [axes]
            for i, col in enumerate(y):
                df.plot(x=x, y=col, ax=axes[i], legend=False, **kwargs)
                axes[i].set_title(col)
                axes[i].set_ylabel(col)
            plt.tight_layout()
            return axes
    else:
        for col in y:
            df.plot(x=x, y=col, ax=ax, **kwargs)
        return ax


def plot_trajectory_listings(trajectory, columns, x: str = 'timestep', **kwargs):
    """Plot listing data from all analyses of a trajectory.

    Parameters
    ----------
    trajectory:
        The trajectory to plot listings for.
    columns:
        Column(s) to plot.
    x:
        X-axis column.  Default ``"timestep"``.

    Returns
    -------
    list[matplotlib.axes.Axes] or None
    """
    import pandas as pd

    if isinstance(columns, str):
        columns = [columns]

    all_dfs: list[pd.DataFrame] = []
    for analysis in trajectory.analyses:
        if analysis.status != 'completed':
            continue
        try:
            df = analysis.listings.to_dataframe()
            if not df.empty:
                df['_analysis'] = analysis.plugin_name
                all_dfs.append(df)
        except Exception:
            continue

    if not all_dfs:
        return None

    combined = pd.concat(all_dfs, ignore_index=True)

    n_cols = len(columns)
    fig, axes = plt.subplots(1, n_cols, figsize=(5 * n_cols, 4))
    if n_cols == 1:
        axes = [axes]

    for i, col in enumerate(columns):
        if col not in combined.columns:
            axes[i].set_title(f'{col} (not found)')
            continue
        for name, group in combined.groupby('_analysis'):
            group.plot(x=x, y=col, ax=axes[i], label=name, **kwargs)
        axes[i].set_title(col)
        axes[i].set_ylabel(col)
        axes[i].legend()

    plt.tight_layout()
    plt.show()
    return axes


def plot_comparison(analyses, column: str, x: str = 'timestep', **kwargs):
    """Compare a single metric across multiple analyses.

    Parameters
    ----------
    analyses:
        List of Analysis objects to compare.
    column:
        The column to compare.
    x:
        X-axis column.  Default ``"timestep"``.

    Returns
    -------
    matplotlib.axes.Axes
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    for analysis in analyses:
        try:
            df = analysis.listings.to_dataframe()
            if column in df.columns:
                label = f'{analysis.plugin_name} ({analysis.id[:8]})'
                df.plot(x=x, y=column, ax=ax, label=label, **kwargs)
        except Exception:
            continue

    ax.set_ylabel(column)
    ax.set_title(f'{column} comparison')
    ax.legend()
    plt.tight_layout()
    plt.show()
    return ax
