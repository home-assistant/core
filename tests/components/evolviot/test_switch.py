"""Test the EvolvIOT switch platform."""

from unittest.mock import AsyncMock, Mock

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
    assert entity.extra_state_attributes["connection_mode"] == "cloud"


async def test_switch_unavailable_without_state(hass: HomeAssistant) -> None:
    """Test switch is unavailable without state."""
    coordinator = _mock_coordinator(hass)
    coordinator.data["states"] = {}
    entity = EvolvIOTSwitch(
        coordinator,
        coordinator.entities["switch.evolviot_switch"],
    )

    assert not entity.available
    assert entity.is_on is None
    assert entity.extra_state_attributes["connection_mode"] == "offline"


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


async def test_switch_sends_cloud_command(hass: HomeAssistant) -> None:
    """Test switch sends cloud command when local command is unavailable."""
    coordinator = _mock_coordinator(hass)
    coordinator.api.async_command = AsyncMock()
    entity = EvolvIOTSwitch(
        coordinator,
        coordinator.entities["switch.evolviot_switch"],
    )
    entity.async_write_ha_state = Mock()
    entity._schedule_refresh = Mock()

    await entity.async_turn_on()

    coordinator.api.async_command.assert_awaited_once_with(
        "switch.evolviot_switch",
        {"command": "turn_on"},
    )
    assert coordinator.states["switch.evolviot_switch"]["state"] == "on"
    entity.async_write_ha_state.assert_called_once()
    entity._schedule_refresh.assert_called_once()


async def test_switch_builds_local_command(hass: HomeAssistant) -> None:
    """Test local command metadata is built."""
    coordinator = _mock_coordinator(hass)
    entity_data = coordinator.entities["switch.evolviot_switch"]
    entity_data["device"]["local_control"] = {
        "device_secret": "secret",
        "endpoint": "control",
    }
    entity = EvolvIOTSwitch(coordinator, entity_data)

    assert entity._local_command({"command": "turn_on"}) == {
        "uid": "user-123",
        "device_id": "SWITCH123",
        "endpoint": "power",
        "device_secret": "secret",
        "switch_name": "power",
        "value": 1,
    }
    assert entity._local_command_value({"command": "turn_off"}) == 0
    assert entity._local_command_value({"command": "toggle"}) is None


async def test_switch_sends_preferred_local_command(hass: HomeAssistant) -> None:
    """Test switch sends preferred local command when local status is available."""
    coordinator = _mock_coordinator(hass)
    entity_data = coordinator.entities["switch.evolviot_switch"]
    entity_data["device"]["local_control"] = {"device_secret": "secret"}
    coordinator.data["states"]["switch.evolviot_switch"]["local_available"] = True
    entity = EvolvIOTSwitch(coordinator, entity_data)
    entity.async_write_ha_state = Mock()
    entity._schedule_refresh = Mock()
    entity._async_send_prefer_local = AsyncMock()

    await entity.async_turn_on()

    entity._async_send_prefer_local.assert_awaited_once()
    entity._schedule_refresh.assert_called_once()
