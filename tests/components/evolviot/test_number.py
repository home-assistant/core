"""Test EvolvIOT number entities."""

from unittest.mock import AsyncMock

from homeassistant.components.evolviot.api import EvolvIOTApi
from homeassistant.components.evolviot.coordinator import EvolvIOTDataUpdateCoordinator
from homeassistant.components.evolviot.number import EvolvIOTBrightnessNumber
from homeassistant.const import UnitOfRatio
from homeassistant.core import HomeAssistant


async def test_brightness_number_properties(hass: HomeAssistant) -> None:
    """Test brightness control is exposed as a number."""
    coordinator = EvolvIOTDataUpdateCoordinator(
        hass,
        AsyncMock(spec=EvolvIOTApi),
        "test-entry",
    )
    coordinator.async_set_updated_data(
        {
            "entities": {
                "switch.evolviot_brightness": {
                    "entity_id": "switch.evolviot_brightness",
                    "unique_id": "LDC123/brightness",
                    "domain": "switch",
                    "name": "LDC brightness",
                },
            },
            "states": {
                "switch.evolviot_brightness": {
                    "available": True,
                    "raw_value": 75,
                    "state": "75",
                },
            },
        }
    )
    entity = EvolvIOTBrightnessNumber(
        coordinator,
        coordinator.entities["switch.evolviot_brightness"],
    )

    assert coordinator.entities_for_domain("number") == [
        coordinator.entities["switch.evolviot_brightness"]
    ]
    assert coordinator.entities_for_domain("switch") == []
    assert entity.native_min_value == 0
    assert entity.native_max_value == 100
    assert entity.native_step == 1
    assert entity.native_unit_of_measurement == UnitOfRatio.PERCENTAGE
    assert entity.native_value == 75


async def test_brightness_number_sends_brightness(hass: HomeAssistant) -> None:
    """Test setting number value sends brightness payload."""
    coordinator = EvolvIOTDataUpdateCoordinator(
        hass,
        AsyncMock(spec=EvolvIOTApi),
        "test-entry",
    )
    coordinator.async_set_updated_data(
        {
            "entities": {
                "number.evolviot_brightness": {
                    "entity_id": "number.evolviot_brightness",
                    "unique_id": "LDC123/brightness",
                    "domain": "number",
                    "name": "LDC brightness",
                },
            },
        }
    )
    entity = EvolvIOTBrightnessNumber(
        coordinator,
        coordinator.entities["number.evolviot_brightness"],
    )
    entity._async_send_command = AsyncMock()

    await entity.async_set_native_value(76.4)

    entity._async_send_command.assert_awaited_once_with({"brightness": 76})
