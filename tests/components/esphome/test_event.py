"""Test ESPHome Events."""

from aioesphomeapi import APIClient, Event, EventInfo
import pytest

from homeassistant.components.event import EventDeviceClass
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant


@pytest.mark.freeze_time("2024-04-24 00:00:00+00:00")
async def test_generic_event_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test a generic event entity and its availability behavior."""
    entity_info = [
        EventInfo(
            object_id="myevent",
            key=1,
            name="my event",
            unique_id="my_event",
            event_types=["type1", "type2"],
            device_class=EventDeviceClass.BUTTON,
        )
    ]
    states = [Event(key=1, event_type="type1")]
    user_service = []
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test initial state
    state = hass.states.get("event.test_myevent")
    assert state is not None
    assert state.state == "2024-04-24T00:00:00.000+00:00"
    assert state.attributes["event_type"] == "type1"

    # Test device becomes unavailable
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_myevent")
    assert state.state == STATE_UNAVAILABLE

    # Test device becomes available again
    await device.mock_connect()
    await hass.async_block_till_done()

    # Event entity should be available immediately without waiting for data
    state = hass.states.get("event.test_myevent")
    assert state.state == "2024-04-24T00:00:00.000+00:00"
    assert state.attributes["event_type"] == "type1"
