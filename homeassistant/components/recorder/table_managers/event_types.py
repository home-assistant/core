"""Support managing EventTypes."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from lru import LRU
from sqlalchemy.orm.session import Session

from homeassistant.core import Event

from ..db_schema import EventTypes
from ..queries import find_event_type_ids
from ..tasks import RefreshEventTypesTask
from ..util import chunked, execute_stmt_lambda_element
from . import BaseLRUTableManager

if TYPE_CHECKING:
    from ..core import Recorder


CACHE_SIZE = 2048


class EventTypeManager(BaseLRUTableManager[EventTypes]):
    """Manage the EventTypes table."""

    def __init__(self, recorder: Recorder) -> None:
        """Initialize the event type manager."""
        super().__init__(recorder, CACHE_SIZE)
        self._non_existent_event_types: LRU[str, None] = LRU(CACHE_SIZE)

    def load(self, events: list[Event], session: Session) -> None:
        """Load the event_type to event_type_ids mapping into memory.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        self.get_many(
            {event.event_type for event in events if event.event_type is not None},
            session,
            True,
        )

    def get(
        self, event_type: str, session: Session, from_recorder: bool = False
    ) -> int | None:
        """Resolve event_type to the event_type_id.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        return self.get_many((event_type,), session)[event_type]

    def get_many(
        self, event_types: Iterable[str], session: Session, from_recorder: bool = False
    ) -> dict[str, int | None]:
        """Resolve event_types to event_type_ids.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        results: dict[str, int | None] = {}
        missing: list[str] = []
        non_existent: list[str] = []

        for event_type in event_types:
            if (event_type_id := self._id_map.get(event_type)) is None:
                if event_type in self._non_existent_event_types:
                    results[event_type] = None
                else:
                    missing.append(event_type)

            results[event_type] = event_type_id

        if not missing:
            return results

        with session.no_autoflush:
            for missing_chunk in chunked(missing, self.recorder.max_bind_vars):
                for event_type_id, event_type in execute_stmt_lambda_element(
                    session, find_event_type_ids(missing_chunk), orm_rows=False
                ):
                    results[event_type] = self._id_map[event_type] = cast(
                        int, event_type_id
                    )

        if non_existent := [
            event_type for event_type in missing if results[event_type] is None
        ]:
            if from_recorder:
                # We are already in the recorder thread so we can update the
                # non-existent event types directly.
                for event_type in non_existent:
                    self._non_existent_event_types[event_type] = None
            else:
                # Queue a task to refresh the event types since its not
                # thread-safe to do it here since we are not in the recorder
                # thread.
                self.recorder.queue_task(RefreshEventTypesTask(non_existent))

        return results

    def add_pending(self, db_event_type: EventTypes) -> None:
        """Add a pending EventTypes that will be committed at the next interval.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        assert db_event_type.event_type is not None
        event_type: str = db_event_type.event_type
        self._pending[event_type] = db_event_type

    def post_commit_pending(self) -> None:
        """Call after commit to load the event_type_ids of the new EventTypes into the LRU.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        for event_type, db_event_types in self._pending.items():
            self._id_map[event_type] = db_event_types.event_type_id
            self.clear_non_existent(event_type)
        self._pending.clear()

    def clear_non_existent(self, event_type: str) -> None:
        """Clear a non-existent event type from the cache.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        self._non_existent_event_types.pop(event_type, None)

    def evict_purged(self, event_types: Iterable[str]) -> None:
        """Evict purged event_types from the cache when they are no longer used.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        for event_type in event_types:
            self._id_map.pop(event_type, None)
