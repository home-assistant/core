"""Test ESPHome Events."""

from aioesphomeapi import APIClient, Event, EventInfo
import pytest

from homeassistant.components.event import EventDeviceClass
from homeassistant.core import HomeAssistant


@pytest.mark.freeze_time("2024-04-24 00:00:00+00:00")
async def test_generic_event_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic event entity."""
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
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("event.test_myevent")
    assert state is not None
    assert state.state == "2024-04-24T00:00:00.000+00:00"
    assert state.attributes["event_type"] == "type1"
