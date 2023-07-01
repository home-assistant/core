"""Support managing StateAttributes."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, cast

from sqlalchemy.orm.session import Session

from homeassistant.core import Event
from homeassistant.helpers.entity import entity_sources
from homeassistant.util.json import JSON_ENCODE_EXCEPTIONS

from . import BaseLRUTableManager
from ..const import SQLITE_MAX_BIND_VARS
from ..db_schema import StateAttributes
from ..queries import get_shared_attributes
from ..util import chunked, execute_stmt_lambda_element

if TYPE_CHECKING:
    from ..core import Recorder

# The number of attribute ids to cache in memory
#
# Based on:
# - The number of overlapping attributes
# - How frequently states with overlapping attributes will change
# - How much memory our low end hardware has
CACHE_SIZE = 2048

_LOGGER = logging.getLogger(__name__)


class StateAttributesManager(BaseLRUTableManager[StateAttributes]):
    """Manage the StateAttributes table."""

    def __init__(
        self, recorder: Recorder, exclude_attributes_by_domain: dict[str, set[str]]
    ) -> None:
        """Initialize the event type manager."""
        super().__init__(recorder, CACHE_SIZE)
        self.active = True  # always active
        self._exclude_attributes_by_domain = exclude_attributes_by_domain
        self._entity_sources = entity_sources(recorder.hass)

    def serialize_from_event(self, event: Event) -> bytes | None:
        """Serialize event data."""
        try:
            return StateAttributes.shared_attrs_bytes_from_event(
                event,
                self._entity_sources,
                self._exclude_attributes_by_domain,
                self.recorder.dialect_name,
            )
        except JSON_ENCODE_EXCEPTIONS as ex:
            _LOGGER.warning(
                "State is not JSON serializable: %s: %s",
                event.data.get("new_state"),
                ex,
            )
            return None

    def load(self, events: list[Event], session: Session) -> None:
        """Load the shared_attrs to attributes_ids mapping into memory from events.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        if hashes := {
            StateAttributes.hash_shared_attrs_bytes(shared_attrs_bytes)
            for event in events
            if (shared_attrs_bytes := self.serialize_from_event(event))
        }:
            self._load_from_hashes(hashes, session)

    def get(self, shared_attr: str, data_hash: int, session: Session) -> int | None:
        """Resolve shared_attrs to the attributes_id.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        return self.get_many(((shared_attr, data_hash),), session)[shared_attr]

    def get_many(
        self, shared_attrs_data_hashes: Iterable[tuple[str, int]], session: Session
    ) -> dict[str, int | None]:
        """Resolve shared_attrs to attributes_ids.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        results: dict[str, int | None] = {}
        missing_hashes: set[int] = set()
        for shared_attrs, data_hash in shared_attrs_data_hashes:
            if (attributes_id := self._id_map.get(shared_attrs)) is None:
                missing_hashes.add(data_hash)

            results[shared_attrs] = attributes_id

        if not missing_hashes:
            return results

        return results | self._load_from_hashes(missing_hashes, session)

    def _load_from_hashes(
        self, hashes: Iterable[int], session: Session
    ) -> dict[str, int | None]:
        """Load the shared_attrs to attributes_ids mapping into memory from a list of hashes.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        results: dict[str, int | None] = {}
        with session.no_autoflush:
            for hashs_chunk in chunked(hashes, SQLITE_MAX_BIND_VARS):
                for attributes_id, shared_attrs in execute_stmt_lambda_element(
                    session, get_shared_attributes(hashs_chunk), orm_rows=False
                ):
                    results[shared_attrs] = self._id_map[shared_attrs] = cast(
                        int, attributes_id
                    )

        return results

    def add_pending(self, db_state_attributes: StateAttributes) -> None:
        """Add a pending StateAttributes that will be committed at the next interval.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        assert db_state_attributes.shared_attrs is not None
        shared_attrs: str = db_state_attributes.shared_attrs
        self._pending[shared_attrs] = db_state_attributes

    def post_commit_pending(self) -> None:
        """Call after commit to load the attributes_ids of the new StateAttributes into the LRU.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        for shared_attrs, db_state_attributes in self._pending.items():
            self._id_map[shared_attrs] = db_state_attributes.attributes_id
        self._pending.clear()

    def evict_purged(self, attributes_ids: set[int]) -> None:
        """Evict purged attributes_ids from the cache when they are no longer used.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        id_map = self._id_map
        state_attributes_ids_reversed = {
            attributes_id: shared_attrs
            for shared_attrs, attributes_id in id_map.items()
        }
        # Evict any purged data from the cache
        for purged_attributes_id in attributes_ids.intersection(
            state_attributes_ids_reversed
        ):
            id_map.pop(state_attributes_ids_reversed[purged_attributes_id], None)
