"""Support managing States."""

from __future__ import annotations

from ..db_schema import States


class StatesManager:
    """Manage the states table."""

    def __init__(self) -> None:
        """Initialize the states manager for linking old_state_id."""
        self._pending: dict[str, States] = {}
        self._last_committed_id: dict[str, int] = {}
        self._last_reported: dict[int, float] = {}

    def pop_pending(self, entity_id: str) -> States | None:
        """Pop a pending state.

        Pending states are states that are in the session but not yet committed.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        return self._pending.pop(entity_id, None)

    def pop_committed(self, entity_id: str) -> int | None:
        """Pop a committed state.

        Committed states are states that have already been committed to the
        database.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        return self._last_committed_id.pop(entity_id, None)

    def add_pending(self, entity_id: str, state: States) -> None:
        """Add a pending state.

        Pending states are states that are in the session but not yet committed.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        self._pending[entity_id] = state

    def update_pending_last_reported(
        self, state_id: int, last_reported_timestamp: float
    ) -> None:
        """Update the last reported timestamp for a state."""
        self._last_reported[state_id] = last_reported_timestamp

    def get_pending_last_reported_timestamp(self) -> dict[int, float]:
        """Return the last reported timestamp for all pending states."""
        return self._last_reported

    def post_commit_pending(self) -> None:
        """Call after commit to load the state_id of the new States into committed.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        for entity_id, db_states in self._pending.items():
            self._last_committed_id[entity_id] = db_states.state_id
        self._pending.clear()
        self._last_reported.clear()

    def reset(self) -> None:
        """Reset after the database has been reset or changed.

        This call is not thread-safe and must be called from the
        recorder thread.
        """
        self._last_committed_id.clear()
        self._pending.clear()

    def evict_purged_state_ids(self, purged_state_ids: set[int]) -> None:
        """Evict purged states from the committed states.

        When we purge states we need to make sure the next call to record a state
        does not link the old_state_id to the purged state.
        """
        # Make a map from the committed state_id to the entity_id
        last_committed_ids = self._last_committed_id
        last_committed_ids_reversed = {
            state_id: entity_id for entity_id, state_id in last_committed_ids.items()
        }

        # Evict any purged state from the old states cache
        for purged_state_id in purged_state_ids.intersection(
            last_committed_ids_reversed
        ):
            last_committed_ids.pop(last_committed_ids_reversed[purged_state_id], None)

    def evict_purged_entity_ids(self, purged_entity_ids: set[str]) -> None:
        """Evict purged entity_ids from the committed states.

        When we purge states we need to make sure the next call to record a state
        does not link the old_state_id to the purged state.
        """
        last_committed_ids = self._last_committed_id
        for entity_id in purged_entity_ids:
            last_committed_ids.pop(entity_id, None)
