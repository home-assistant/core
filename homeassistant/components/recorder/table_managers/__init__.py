"""Managers for each table."""

from typing import TYPE_CHECKING, Generic, TypeVar

from lru import LRU

if TYPE_CHECKING:
    from ..core import Recorder

_DataT = TypeVar("_DataT")


class BaseTableManager(Generic[_DataT]):
    """Base class for table managers."""

    _id_map: "LRU[str, int]"

    def __init__(self, recorder: "Recorder") -> None:
        """Initialize the table manager.

        The table manager is responsible for managing the id mappings
        for a table. When data is committed to the database, the
        manager will move the data from the pending to the id map.
        """
        self.active = False
        self.recorder = recorder
        self._pending: dict[str, _DataT] = {}

    def get_from_cache(self, data: str) -> int | None:
        """Resolve data to the id without accessing the underlying database.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        return self._id_map.get(data)

    def get_pending(self, shared_data: str) -> _DataT | None:
        """Get pending data that have not be assigned ids yet.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        return self._pending.get(shared_data)

    def reset(self) -> None:
        """Reset after the database has been reset or changed.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        self._id_map.clear()
        self._pending.clear()


class BaseLRUTableManager(BaseTableManager[_DataT]):
    """Base class for LRU table managers."""

    def __init__(self, recorder: "Recorder", lru_size: int) -> None:
        """Initialize the LRU table manager.

        We keep track of the most recently used items
        and evict the least recently used items when the cache is full.
        """
        super().__init__(recorder)
        self._id_map = LRU(lru_size)

    def adjust_lru_size(self, new_size: int) -> None:
        """Adjust the LRU cache size.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        lru = self._id_map
        if new_size > lru.get_size():
            lru.set_size(new_size)
