"""Tests for the Roon event entity."""


from unittest.mock import MagicMock

from homeassistant.components.event import ATTR_EVENT_TYPE, EventDeviceClass
from homeassistant.components.roon.event import RoonEventEntity


async def test_event() -> None:
    """Test the roon event entity."""
    event = RoonEventEntity("server", "test")
    event.async_write_ha_state = MagicMock()

    # Test retrieving data from entity
    assert event.name == "test volume control"
    assert event.event_types == ["volume_up", "volume_down"]
    assert event.device_class == EventDeviceClass.BUTTON

    # Test triggering an invalid event
    event._roonapi_volume_callback("control_key", "invalid", 1)
    assert event.state_attributes == {ATTR_EVENT_TYPE: None}

    # Test triggering volume up
    event._roonapi_volume_callback("control_key", "set_volume", 1)
    assert event.state_attributes == {ATTR_EVENT_TYPE: "volume_up"}

    # Test triggering volume down
    event._roonapi_volume_callback("control_key", "set_volume", -1)
    assert event.state_attributes == {ATTR_EVENT_TYPE: "volume_down"}
