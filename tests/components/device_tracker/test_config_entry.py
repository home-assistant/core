"""Test Device Tracker config entry things."""
from homeassistant.components.device_tracker import config_entry


def test_tracker_entity():
    """Test tracker entity."""

    class TestEntry(config_entry.TrackerEntity):
        """Mock tracker class."""

        should_poll = False

    instance = TestEntry()

    assert instance.force_update

    instance.should_poll = True

    assert not instance.force_update
