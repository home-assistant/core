"""Test EvolvIOT light entities."""

from unittest.mock import AsyncMock

from homeassistant.components.evolviot.api import EvolvIOTApi
from homeassistant.components.evolviot.coordinator import EvolvIOTDataUpdateCoordinator
from homeassistant.components.evolviot.light import EvolvIOTColorLight
from homeassistant.components.light import ATTR_RGB_COLOR, ColorMode
from homeassistant.core import HomeAssistant


def _coordinator(hass: HomeAssistant) -> EvolvIOTDataUpdateCoordinator:
    """Return a coordinator with color data."""
    coordinator = EvolvIOTDataUpdateCoordinator(
        hass,
        AsyncMock(spec=EvolvIOTApi),
        "test-entry",
    )
    coordinator.async_set_updated_data(
        {
            "entities": {
                "color.evolviot_color": {
                    "entity_id": "color.evolviot_color",
                    "unique_id": "LDC123/color",
                    "domain": "color",
                    "name": "Living Room Strip Color",
                    "control": {"key": "color"},
                },
            },
            "states": {
                "color.evolviot_color": {
                    "available": True,
                    "raw_value": "255,0,0",
                    "state": "255,0,0",
                },
            },
        }
    )
    return coordinator


async def test_color_light_properties(hass: HomeAssistant) -> None:
    """Test color control is exposed as an RGB light."""
    coordinator = _coordinator(hass)
    entity = EvolvIOTColorLight(
        coordinator,
        coordinator.entities["color.evolviot_color"],
    )

    assert entity.supported_color_modes == {ColorMode.RGB}
    assert entity.color_mode is ColorMode.RGB
    assert entity.is_on is True
    assert entity.rgb_color == (255, 0, 0)


async def test_color_light_sends_rgb_value(hass: HomeAssistant) -> None:
    """Test setting color sends an RGB value payload."""
    coordinator = _coordinator(hass)
    entity = EvolvIOTColorLight(
        coordinator,
        coordinator.entities["color.evolviot_color"],
    )
    entity._async_send_command = AsyncMock()

    await entity.async_turn_on(**{ATTR_RGB_COLOR: (0, 128, 255)})

    entity._async_send_command.assert_awaited_once_with({"value": "0,128,255"})


async def test_stale_switch_color_entity_is_classified_as_color(
    hass: HomeAssistant,
) -> None:
    """Test stale switch color metadata is classified as color."""
    coordinator = EvolvIOTDataUpdateCoordinator(
        hass,
        AsyncMock(spec=EvolvIOTApi),
        "test-entry",
    )
    coordinator.async_set_updated_data(
        {
            "entities": {
                "switch.evolviot_color": {
                    "entity_id": "switch.evolviot_color",
                    "unique_id": "LDC123/color",
                    "domain": "switch",
                    "control": {
                        "key": "color",
                        "presentation": "color_palette",
                    },
                    "capabilities": {"supports_color": True},
                },
            },
        }
    )

    assert coordinator.entities_for_domain("color") == [
        coordinator.entities["switch.evolviot_color"]
    ]
    assert coordinator.entities_for_domain("switch") == []
