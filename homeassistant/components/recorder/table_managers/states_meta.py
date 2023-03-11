"""Support managing StatesMeta."""
from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from lru import LRU  # pylint: disable=no-name-in-module
from sqlalchemy.orm.session import Session

from homeassistant.core import Event

from ..db_schema import StatesMeta
from ..queries import find_states_metadata_ids

CACHE_SIZE = 8192


class EventTypeManager:
    """Manage the EventTypes table."""

    def __init__(self) -> None:
        """Initialize the event type manager."""
        self._id_map: dict[str, int] = LRU(CACHE_SIZE)
        self._pending: dict[str, StatesMeta] = {}
        self.active = False

    def load(self, events: list[Event], session: Session) -> None:
        """Load the entity_id to metadata_id mapping into memory."""
        self.get_many(
            (
                event.data["new_state"].entity_id
                for event in events
                if event.data.get("new_state") is not None
            ),
            session,
        )

    def get(self, entity_id: str, session: Session) -> int | None:
        """Resolve entity_id to the metadata_id."""
        return self.get_many((entity_id,), session)[entity_id]

    def get_many(
        self, entity_ids: Iterable[str], session: Session
    ) -> dict[str, int | None]:
        """Resolve entity_id to metadata_id."""
        results: dict[str, int | None] = {}
        missing: list[str] = []
        for entity_id in entity_ids:
            if (metadata_id := self._id_map.get(entity_id)) is None:
                missing.append(entity_id)

            results[entity_id] = metadata_id

        if not missing:
            return results

        with session.no_autoflush:
            for metadata_id, entity_id in session.execute(
                find_states_metadata_ids(missing)
            ):
                results[entity_id] = self._id_map[entity_id] = cast(int, metadata_id)

        return results

    def get_pending(self, entity_id: str) -> StatesMeta | None:
        """Get pending StatesMeta that have not be assigned ids yet."""
        return self._pending.get(entity_id)

    def add_pending(self, db_states_meta: StatesMeta) -> None:
        """Add a pending StatesMeta that will be committed at the next interval."""
        assert db_states_meta.entity_id is not None
        entity_id: str = db_states_meta.entity_id
        self._pending[entity_id] = db_states_meta

    def post_commit_pending(self) -> None:
        """Call after commit to load the metadata_ids of the new StatesMeta into the LRU."""
        for entity_id, db_states_meta in self._pending.items():
            self._id_map[entity_id] = db_states_meta.metadata_id
        self._pending.clear()

    def reset(self) -> None:
        """Reset the states meta manager after the database has been reset or changed."""
        self._id_map.clear()
        self._pending.clear()

    def evict_purged(self, entity_ids: Iterable[str]) -> None:
        """Evict purged event_types from the cache when they are no longer used."""
        for entity_id in entity_ids:
            self._id_map.pop(entity_id, None)
