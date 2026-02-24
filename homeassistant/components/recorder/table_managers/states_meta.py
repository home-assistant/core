"""Support managing StatesMeta."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from queue import SimpleQueue
from typing import TYPE_CHECKING, cast

from sqlalchemy.orm.session import Session

from homeassistant.core import Event, EventStateChangedData
from homeassistant.util.collection import chunked_or_all

from ..db_schema import StatesMeta
from ..queries import find_all_states_metadata_ids, find_states_metadata_ids
from ..util import execute_stmt_lambda_element
from . import BaseLRUTableManager

if TYPE_CHECKING:
    from ..core import Recorder

CACHE_SIZE = 8192


class StatesMetaManager(BaseLRUTableManager[StatesMeta]):
    """Manage the StatesMeta table."""

    def __init__(self, recorder: Recorder) -> None:
        """Initialize the states meta manager."""
        self._did_first_load = False
        # Thread-safe queue for entity_id renames from the event loop.
        # Items are (old_entity_id, new_entity_id) tuples.
        self._rename_queue: SimpleQueue[tuple[str, str]] = SimpleQueue()
        # Recorder-thread-only dict mapping new_entity_id -> old_entity_id
        # for renames that haven't been applied to the database yet.
        self._pending_rename: dict[str, str] = {}
        super().__init__(recorder, CACHE_SIZE)

    def queue_rename(self, old_entity_id: str, new_entity_id: str) -> None:
        """Queue an entity_id rename notification.

        This method is thread-safe and is called from the event loop
        to notify the recorder thread about a pending entity_id rename.
        """
        self._rename_queue.put((old_entity_id, new_entity_id))

    def drain_pending_renames(self) -> None:
        """Drain the rename queue into the pending rename dict.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        while not self._rename_queue.empty():
            old_entity_id, new_entity_id = self._rename_queue.get_nowait()
            self._pending_rename[new_entity_id] = old_entity_id

    def load(
        self, events: list[Event[EventStateChangedData]], session: Session
    ) -> None:
        """Load the entity_id to metadata_id mapping into memory.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        self._did_first_load = True
        self.get_many(
            {
                new_state.entity_id
                for event in events
                if (new_state := event.data["new_state"]) is not None
            },
            session,
            True,
        )

    def get(self, entity_id: str, session: Session, from_recorder: bool) -> int | None:
        """Resolve entity_id to the metadata_id.

        This call is not thread-safe after startup since
        purge can remove all references to an entity_id.

        When calling this method from the recorder thread, set
        from_recorder to True to ensure any missing entity_ids
        are added to the cache.
        """
        return self.get_many((entity_id,), session, from_recorder)[entity_id]

    def get_metadata_id_to_entity_id(self, session: Session) -> dict[int, str]:
        """Resolve all entity_ids to metadata_ids.

        This call is always thread-safe.
        """
        with session.no_autoflush:
            return dict(
                cast(
                    Sequence[tuple[int, str]],
                    execute_stmt_lambda_element(
                        session, find_all_states_metadata_ids(), orm_rows=False
                    ),
                )
            )

    def get_many(
        self, entity_ids: Iterable[str], session: Session, from_recorder: bool
    ) -> dict[str, int | None]:
        """Resolve entity_id to metadata_id.

        This call is not thread-safe after startup since
        purge can remove all references to an entity_id.

        When calling this method from the recorder thread, set
        from_recorder to True to ensure any missing entity_ids
        are added to the cache.
        """
        results: dict[str, int | None] = {}
        missing: list[str] = []
        for entity_id in entity_ids:
            if (metadata_id := self._id_map.get(entity_id)) is None:
                missing.append(entity_id)

            results[entity_id] = metadata_id

        if not missing:
            return results

        # Only update the cache if we are in the recorder thread
        # or the recorder event loop has not started yet since
        # there is a chance that we could have just deleted all
        # instances of an entity_id from the database via purge
        # and we do not want to add it back to the cache from another
        # thread (history query).
        update_cache = from_recorder or not self._did_first_load

        with session.no_autoflush:
            for missing_chunk in chunked_or_all(missing, self.recorder.max_bind_vars):
                for metadata_id, entity_id in execute_stmt_lambda_element(
                    session, find_states_metadata_ids(missing_chunk)
                ):
                    metadata_id = cast(int, metadata_id)
                    results[entity_id] = metadata_id

                    if update_cache:
                        self._id_map[entity_id] = metadata_id

        if not from_recorder:
            return results

        # Check pending renames for any entity_ids still not resolved.
        # If an entity_id was renamed but the database hasn't been updated
        # yet, we can resolve the new entity_id by looking up the old one.
        pending_rename = self._pending_rename
        for entity_id in missing:
            if (
                results.get(entity_id) is None
                and (old_entity_id := pending_rename.get(entity_id)) is not None
                and (metadata_id := self._id_map.get(old_entity_id)) is not None
            ):
                results[entity_id] = metadata_id

        return results

    def add_pending(self, db_states_meta: StatesMeta) -> None:
        """Add a pending StatesMeta that will be committed at the next interval.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        assert db_states_meta.entity_id is not None
        entity_id: str = db_states_meta.entity_id
        self._pending[entity_id] = db_states_meta

    def post_commit_pending(self) -> None:
        """Call after commit to load the metadata_ids of the new StatesMeta into the LRU.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        for entity_id, db_states_meta in self._pending.items():
            self._id_map[entity_id] = db_states_meta.metadata_id
        self._pending.clear()

    def evict_purged(self, entity_ids: Iterable[str]) -> None:
        """Evict purged event_types from the cache when they are no longer used.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        for entity_id in entity_ids:
            self._id_map.pop(entity_id, None)

    def update_metadata(
        self,
        session: Session,
        entity_id: str,
        new_entity_id: str,
    ) -> bool:
        """Update states metadata for an entity_id."""
        # Clear the pending rename before the collision check so
        # get() doesn't resolve new_entity_id via the side channel.
        self._pending_rename.pop(new_entity_id, None)
        if self.get(new_entity_id, session, True) is not None:
            # If the new entity id already exists we have
            # a collision and should not update.
            return False
        metadata_id = self._id_map.get(entity_id)
        session.query(StatesMeta).filter(StatesMeta.entity_id == entity_id).update(
            {StatesMeta.entity_id: new_entity_id}
        )
        self._id_map.pop(entity_id, None)
        if metadata_id is not None:
            self._id_map[new_entity_id] = metadata_id
        return True
