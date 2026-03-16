"""Base classes for Volt API resources and lazy-paginating collections.

:class:`BaseResource` wraps a single API entity (trajectory, analysis,
frame, …).  :class:`BaseCollection` provides transparent lazy pagination
over a list endpoint and exposes ``__iter__``, ``__getitem__``,
``__len__``, ``to_dataframe()``, etc.
"""

from __future__ import annotations

from typing import Generic, Iterator, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from voltsdk.http import HttpTransport

T = TypeVar('T', bound='BaseResource')


class BaseResource:
    """Base class for all Volt API resources."""

    def __init__(self, client: HttpTransport, data: dict) -> None:
        self._client = client
        self._data = data

    # ------------------------------------------------------------------
    # Common accessors
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        """MongoDB ``_id`` of this resource."""
        return self._data.get('_id', '')

    @property
    def raw(self) -> dict:
        """The underlying API response dictionary (read-only)."""
        return self._data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get(self, key: str, default=None):
        """Shortcut for ``self._data.get(key, default)``."""
        return self._data.get(key, default)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id}>'


class BaseCollection(Generic[T]):
    """Lazy, auto-paginating collection of resources.

    Iterating over a :class:`BaseCollection` transparently fetches pages
    from the API as needed.  Individual items can also be accessed via
    ``collection[index]``.  Call :meth:`list` to eagerly materialise every
    item, or :meth:`to_dataframe` for a pandas DataFrame.

    Parameters
    ----------
    client:
        The :class:`~voltsdk.http.HttpTransport` instance.
    path:
        API path for the list endpoint (without ``base_url``).
    resource_cls:
        The :class:`BaseResource` subclass to wrap each response row.
    params:
        Extra query-string parameters forwarded on every page fetch.
    page_size:
        Number of items requested per page (default ``100``).
    """

    def __init__(
        self,
        client: HttpTransport,
        path: str,
        resource_cls: type[T] | None = None,
        params: dict | None = None,
        page_size: int = 100,
    ) -> None:
        self._client = client
        self._path = path
        self._resource_cls = resource_cls
        self._params = params or {}
        self._page_size = page_size

        # Internal cache for indexed access
        self._cache: list[T] = []
        self._total: int | None = None
        self._fetched_pages: int = 0

    # ------------------------------------------------------------------
    # Iteration & indexing
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[T]:
        """Lazily paginate through all results."""
        page = 1
        while True:
            items = self._fetch_page(page)
            if not items:
                break
            for item in items:
                yield self._wrap(item)
            if len(items) < self._page_size:
                break
            page += 1

    def __getitem__(self, index: int) -> T:
        """Access by index with automatic page fetching."""
        if index < 0:
            # Negative index → need total length
            index = len(self) + index
        self._ensure_fetched_through(index)
        return self._cache[index]

    def __len__(self) -> int:
        if self._total is None:
            self._fetch_page(1)
        return self._total or 0

    def __bool__(self) -> bool:
        return len(self) > 0

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def list(self, **kwargs) -> list[T]:
        """Eagerly fetch **all** items.

        .. warning::

            On very large collections this may be slow.  Prefer iterating
            lazily (``for item in collection: …``) when possible.
        """
        return list(self)

    def first(self) -> T | None:
        """Fetch the first item only, or ``None`` if empty."""
        try:
            return self[0]
        except IndexError:
            return None

    def to_dataframe(self):
        """Convert the entire collection to a :class:`~pandas.DataFrame`.

        Each row corresponds to one resource; columns are the raw API
        keys.
        """
        import pandas as pd
        return pd.DataFrame([item.raw for item in self])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wrap(self, data: dict) -> T:
        """Wrap a raw dict in the appropriate resource class."""
        if self._resource_cls is None:
            raise TypeError('_resource_cls must be set on the collection')
        return self._resource_cls(self._client, data)

    def _fetch_page(self, page: int) -> list[dict]:
        """Fetch a single page from the API and update the cache."""
        params = {**self._params, 'page': page, 'limit': self._page_size}
        response = self._client.get(self._path, params=params)

        # The server wraps paginated lists in ``{data: [...], total, page, …}``
        # but ``HttpTransport.get`` already unwraps the outer ``{status, data}``
        # envelope, so ``response`` here is the inner ``data`` object.
        if isinstance(response, dict):
            items = response.get('data', [])
            if 'total' in response:
                self._total = response['total']
        elif isinstance(response, list):
            items = response
        else:
            items = []

        if not isinstance(items, list):
            items = []

        # Extend local cache
        if page > self._fetched_pages:
            for item in items:
                self._cache.append(self._wrap(item))
            self._fetched_pages = page

        return items

    def _ensure_fetched_through(self, index: int) -> None:
        """Fetch pages until the cache covers *index*."""
        while index >= len(self._cache):
            next_page = self._fetched_pages + 1
            items = self._fetch_page(next_page)
            if not items:
                break

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        if self._total is not None:
            return f'<{cls} total={self._total}>'
        return f'<{cls} (not yet fetched)>'
