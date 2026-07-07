"""Test the EvolvIOT switch platform."""

from unittest.mock import AsyncMock

from homeassistant.components.evolviot.coordinator import EvolvIOTDataUpdateCoordinator
from homeassistant.components.evolviot.switch import EvolvIOTSwitch
from homeassistant.core import HomeAssistant


def _mock_coordinator(hass: HomeAssistant) -> EvolvIOTDataUpdateCoordinator:
    """Return a coordinator with switch data."""
    coordinator = EvolvIOTDataUpdateCoordinator(hass, AsyncMock(), "entry-id")
    coordinator.data = {
        "user_id": "user-123",
        "entities": {
            "switch.evolviot_switch": {
                "entity_id": "switch.evolviot_switch",
                "unique_id": "SWITCH123/power",
                "domain": "switch",
                "name": "Living Room Switch",
                "device": {
                    "id": "SWITCH123",
                    "name": "Living Room",
                    "manufacturer": "EvolvIOT",
                    "model": "Switch",
                },
                "control": {"key": "power"},
            }
        },
        "states": {
            "switch.evolviot_switch": {
                "entity_id": "switch.evolviot_switch",
                "available": True,
                "state": "on",
                "raw_value": 1,
            }
        },
    }
    return coordinator


async def test_switch_properties(hass: HomeAssistant) -> None:
    """Test switch properties."""
    coordinator = _mock_coordinator(hass)

    entity = EvolvIOTSwitch(
        coordinator,
        coordinator.entities["switch.evolviot_switch"],
    )

    assert entity.unique_id == "SWITCH123/power"
    assert entity.name == "Living Room Switch"
    assert entity.available
    assert entity.is_on
    assert entity.extra_state_attributes["evolviot_entity_id"] == (
        "switch.evolviot_switch"
    )
    assert entity.extra_state_attributes["raw_value"] == 1


async def test_switch_sends_commands(hass: HomeAssistant) -> None:
    """Test switch commands."""
    coordinator = _mock_coordinator(hass)
    entity = EvolvIOTSwitch(
        coordinator,
        coordinator.entities["switch.evolviot_switch"],
    )
    entity._async_send_command = AsyncMock()

    await entity.async_turn_on()
    entity._async_send_command.assert_awaited_once_with({"command": "turn_on"})

    entity._async_send_command.reset_mock()

    await entity.async_turn_off()
    entity._async_send_command.assert_awaited_once_with({"command": "turn_off"})
