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
