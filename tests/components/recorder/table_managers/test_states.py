"""The tests for the recorder states manager."""

from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.table_managers.states import StatesManager


def test_reset_preserves_oldest_ts() -> None:
    """Test reset() keeps oldest_ts."""
    manager = StatesManager()
    manager.add_pending("sensor.test", States(last_updated_ts=123.0))

    manager.reset()

    assert manager.oldest_ts == 123.0
    assert manager.pop_pending("sensor.test") is None


def test_add_pending_after_reset_does_not_reseed_oldest_ts() -> None:
    """Test add_pending after reset does not seed oldest_ts from the new state."""
    manager = StatesManager()
    manager.add_pending("sensor.test", States(last_updated_ts=10.0))
    manager.reset()
    manager.add_pending("sensor.test", States(last_updated_ts=99.0))

    assert manager.oldest_ts == 10.0


def test_evict_purged_state_ids_drops_pending_last_reported() -> None:
    """Test purged states have no pending last reported update."""
    manager = StatesManager()
    manager.update_pending_last_reported(1, 123.0)
    manager.update_pending_last_reported(2, 456.0)

    manager.evict_purged_state_ids({1, 3})

    assert manager.get_pending_last_reported_timestamp() == {2: 456.0}
