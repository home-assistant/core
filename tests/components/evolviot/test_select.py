"""Test EvolvIOT select entities."""

from unittest.mock import AsyncMock

from homeassistant.components.evolviot.api import EvolvIOTApi
from homeassistant.components.evolviot.coordinator import EvolvIOTDataUpdateCoordinator
from homeassistant.components.evolviot.select import EvolvIOTSelect
from homeassistant.core import HomeAssistant


def _coordinator(hass: HomeAssistant) -> EvolvIOTDataUpdateCoordinator:
    """Return a coordinator with select data."""
    coordinator = EvolvIOTDataUpdateCoordinator(
        hass,
        AsyncMock(spec=EvolvIOTApi),
        "test-entry",
    )
    coordinator.async_set_updated_data(
        {
            "entities": {
                "select.evolviot_pattern": {
                    "entity_id": "select.evolviot_pattern",
                    "unique_id": "LDC123/pattern",
                    "domain": "select",
                    "name": "Living Room Strip Pattern",
                    "control": {
                        "options": [
                            {"label": "rainbow", "value": "rainbow"},
                            {"label": "pulse", "value": "pulse"},
                            {"label": "wave", "value": "wave"},
                        ],
                    },
                },
            },
            "states": {
                "select.evolviot_pattern": {
                    "available": True,
                    "raw_value": "rainbow",
                    "state": "rainbow",
                },
            },
        }
    )
    return coordinator


async def test_select_options_and_current_option(hass: HomeAssistant) -> None:
    """Test select options and current option."""
    coordinator = _coordinator(hass)
    entity = EvolvIOTSelect(
        coordinator,
        coordinator.entities["select.evolviot_pattern"],
    )

    assert entity.current_option == "rainbow"
    assert entity.options == ["rainbow", "pulse", "wave"]


async def test_select_option_sends_value(hass: HomeAssistant) -> None:
    """Test selecting an option sends a value payload."""
    coordinator = _coordinator(hass)
    entity = EvolvIOTSelect(
        coordinator,
        coordinator.entities["select.evolviot_pattern"],
    )
    entity._async_send_command = AsyncMock()

    await entity.async_select_option("wave")

    entity._async_send_command.assert_awaited_once_with({"value": "wave"})


async def test_stale_switch_pattern_entity_is_classified_as_select(
    hass: HomeAssistant,
) -> None:
    """Test stale switch pattern metadata is classified as select."""
    coordinator = EvolvIOTDataUpdateCoordinator(
        hass,
        AsyncMock(spec=EvolvIOTApi),
        "test-entry",
    )
    coordinator.async_set_updated_data(
        {
            "entities": {
                "switch.evolviot_pattern": {
                    "entity_id": "switch.evolviot_pattern",
                    "unique_id": "LDC123/pattern",
                    "domain": "switch",
                    "control": {
                        "key": "pattern",
                        "presentation": "dropdown",
                        "value_list": ["rainbow", "pulse"],
                    },
                    "capabilities": {"supports_select": True},
                },
            },
        }
    )

    assert coordinator.entities_for_domain("select") == [
        coordinator.entities["switch.evolviot_pattern"]
    ]
    assert coordinator.entities_for_domain("switch") == []
