"""Test dreo fan platform."""

from unittest.mock import MagicMock, patch

from pydreo.exceptions import DreoException
import pytest

from homeassistant.components.dreo.fan import async_setup_entry
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration


async def test_fan_setup_and_device_info(hass: HomeAssistant) -> None:
    """Test fan setup and device info."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-123",
                "model": "DR-HTF001S",
                "deviceName": "Living Room Fan",
                "moduleFirmwareVersion": "1.0.0",
                "mcuFirmwareVersion": "2.0.0",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "mode": "Auto",
            "speed": 3,
            "oscillate": True,
        }

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Ensure coordinator data is loaded
        coordinator = config_entry.runtime_data.coordinators["test-fan-123"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("fan.living_room_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert state.attributes[ATTR_PRESET_MODE] == "Auto"
    assert state.attributes[ATTR_OSCILLATING] is True

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={("dreo", "test-fan-123")})
    assert device is not None
    assert device.name == "Living Room Fan"
    assert device.model == "DR-HTF001S"
    assert device.manufacturer == "Dreo"
    assert device.sw_version == "1.0.0"
    assert device.hw_version == "2.0.0"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("fan.living_room_fan")
    assert entity is not None
    assert entity.unique_id == "test-fan-123_fan"
    assert entity.device_id == device.id


async def test_fan_turn_on_service(hass: HomeAssistant) -> None:
    """Test fan turn on service."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-456",
                "model": "DR-HTF001S",
                "deviceName": "Bedroom Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": False,
            "connected": True,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("fan.bedroom_fan")
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.bedroom_fan"},
        blocking=True,
    )

    mock_client.update_status.assert_called_with("test-fan-456", power_switch=True)


async def test_fan_turn_off_service(hass: HomeAssistant) -> None:
    """Test fan turn off service."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-789",
                "model": "DR-HTF001S",
                "deviceName": "Kitchen Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.kitchen_fan"},
        blocking=True,
    )

    mock_client.update_status.assert_called_with("test-fan-789", power_switch=False)


async def test_fan_set_percentage_service(hass: HomeAssistant) -> None:
    """Test fan set percentage service."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-abc",
                "model": "DR-HTF001S",
                "deviceName": "Office Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": False,
            "connected": True,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        "set_percentage",
        {ATTR_ENTITY_ID: "fan.office_fan", ATTR_PERCENTAGE: 75},
        blocking=True,
    )

    mock_client.update_status.assert_called_with(
        "test-fan-abc", power_switch=True, speed=5
    )


async def test_fan_set_preset_mode_service(hass: HomeAssistant) -> None:
    """Test fan set preset mode service."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-def",
                "model": "DR-HTF001S",
                "deviceName": "Garage Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "mode": "Auto",
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        "set_preset_mode",
        {ATTR_ENTITY_ID: "fan.garage_fan", ATTR_PRESET_MODE: "Sleep"},
        blocking=True,
    )

    mock_client.update_status.assert_called_with(
        "test-fan-def", power_switch=True, mode="Sleep"
    )


async def test_fan_oscillate_service(hass: HomeAssistant) -> None:
    """Test fan oscillate service."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-ghi",
                "model": "DR-HTF001S",
                "deviceName": "Patio Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "oscillate": False,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        "oscillate",
        {ATTR_ENTITY_ID: "fan.patio_fan", ATTR_OSCILLATING: True},
        blocking=True,
    )

    mock_client.update_status.assert_called_with(
        "test-fan-ghi", power_switch=True, oscillate=True
    )


async def test_fan_unavailable_when_disconnected(hass: HomeAssistant) -> None:
    """Test fan shows unavailable when device is disconnected."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-offline",
                "model": "DR-HTF001S",
                "deviceName": "Offline Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": False,
            "connected": False,
        }

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.offline_fan")
    assert state is not None
    assert state.state == STATE_OFF


async def test_fan_coordinator_error_handling(hass: HomeAssistant) -> None:
    """Test fan coordinator error handling."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-error",
                "model": "DR-HTF001S",
                "deviceName": "Error Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.side_effect = [
            {"power_switch": True, "connected": True},
            DreoException("API Error"),
        ]

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("fan.error_fan")
    assert state is not None
    assert state.state == STATE_OFF


async def test_fan_state_updates_from_coordinator(hass: HomeAssistant) -> None:
    """Test fan state updates when coordinator data changes."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-update",
                "model": "DR-HTF001S",
                "deviceName": "Update Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]

        status_responses = [
            {"power_switch": False, "connected": True},
            {"power_switch": True, "connected": True, "speed": 4, "mode": "Natural"},
        ]
        mock_client.get_status.side_effect = status_responses

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.update_fan")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0

    coordinator = config_entry.runtime_data.coordinators["test-fan-update"]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("fan.update_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 66
    assert state.attributes[ATTR_PRESET_MODE] == "Natural"


async def test_fan_unsupported_device_not_created(hass: HomeAssistant) -> None:
    """Test that unsupported devices are not created as fan entities."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-unsupported",
                "model": "UNKNOWN-MODEL",
                "deviceName": "Unsupported Device",
                "deviceType": "heater",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("fan.unsupported_device") is None

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    fan_entities = [e for e in entities if e.domain == FAN_DOMAIN]
    assert len(fan_entities) == 0


async def test_fan_service_error_handling(hass: HomeAssistant) -> None:
    """Test fan service call error handling."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-service-error",
                "model": "DR-HTF001S",
                "deviceName": "Service Error Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": False,
            "connected": True,
        }
        mock_client.update_status.side_effect = DreoException("Service error")

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "fan.service_error_fan"},
            blocking=True,
        )


async def test_fan_setup_missing_coordinator(hass: HomeAssistant) -> None:
    """Test fan setup when coordinator is missing from coordinators dict."""
    with (
        patch("homeassistant.components.dreo.DreoClient") as mock_client_class,
        patch("homeassistant.components.dreo.fan._LOGGER") as mock_logger,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-missing-coord",
                "model": "DR-HTF001S",
                "deviceName": "Missing Coordinator Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        original_coordinators = config_entry.runtime_data.coordinators.copy()
        config_entry.runtime_data.coordinators.clear()

        await async_setup_entry(
            hass,
            config_entry,
            lambda entities, update_before_add=False, *, config_subentry_id=None: None,
        )

        mock_logger.error.assert_called_with(
            "Coordinator not found for device %s", "test-fan-missing-coord"
        )

        config_entry.runtime_data.coordinators.update(original_coordinators)


async def test_fan_setup_no_devices(hass: HomeAssistant) -> None:
    """Test fan setup when no devices are found."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = []

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    fan_entities = [e for e in entities if e.domain == FAN_DOMAIN]
    assert len(fan_entities) == 0


async def test_fan_setup_missing_device_info(hass: HomeAssistant) -> None:
    """Test fan setup with devices missing required information."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "model": "DR-HTF001S",
                "deviceName": "No SN Fan",
                "deviceType": "fan",
                "config": {"preset_modes": ["Sleep", "Auto"], "speed_range": [1, 6]},
            },
            {
                "deviceSn": "",
                "model": "DR-HTF001S",
                "deviceName": "Empty SN Fan",
                "deviceType": "fan",
                "config": {"preset_modes": ["Sleep", "Auto"], "speed_range": [1, 6]},
            },
            {
                "deviceSn": "test-no-type",
                "model": "DR-HTF001S",
                "deviceName": "No Type Fan",
                "config": {"preset_modes": ["Sleep", "Auto"], "speed_range": [1, 6]},
            },
        ]

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    fan_entities = [e for e in entities if e.domain == FAN_DOMAIN]
    assert len(fan_entities) == 0


async def test_fan_state_with_none_available(hass: HomeAssistant) -> None:
    """Test fan state when coordinator data has available = None."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-none-available",
                "model": "DR-HTF001S",
                "deviceName": "None Available Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinators["test-fan-none-available"]

    if coordinator.data:
        coordinator.data.available = None
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

    state = hass.states.get("fan.none_available_fan")
    assert state is not None
    assert state.state == STATE_OFF


async def test_fan_execute_command_with_zero_speed(hass: HomeAssistant) -> None:
    """Test fan command execution with zero speed percentage."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-zero-speed",
                "model": "DR-HTF001S",
                "deviceName": "Zero Speed Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
            "speed": 3,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        "set_percentage",
        {ATTR_ENTITY_ID: "fan.zero_speed_fan", ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    mock_client.update_status.assert_called_with(
        "test-fan-zero-speed", power_switch=False
    )


async def test_fan_execute_command_without_speed_range(hass: HomeAssistant) -> None:
    """Test fan command execution when speed_range is not configured."""
    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-fan-no-speed-range",
                "model": "DR-HTF001S",
                "deviceName": "No Speed Range Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": False,
            "connected": True,
        }
        mock_client.update_status = MagicMock()

        config_entry = await init_integration(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        "set_percentage",
        {ATTR_ENTITY_ID: "fan.no_speed_range_fan", ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    mock_client.update_status.assert_called_with(
        "test-fan-no-speed-range", power_switch=True
    )
