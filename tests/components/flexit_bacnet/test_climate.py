"""Tests for the Flexit Nordic (BACnet) climate entity."""
from unittest.mock import AsyncMock

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_STEP,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    HVACMode,
)
from homeassistant.const import PRECISION_HALVES, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.flexit_bacnet import setup_with_selected_platforms

ENTITY_CLIMATE = "climate.device_name"


async def test_climate_entity(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    state = hass.states.get(ENTITY_CLIMATE)

    assert state.attributes.get("name") is None
    assert state.state == HVACMode.FAN_ONLY
    assert state.attributes.get(ATTR_PRESET_MODES) == [
        PRESET_AWAY,
        PRESET_HOME,
        PRESET_BOOST,
    ]
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVACMode.OFF,
        HVACMode.FAN_ONLY,
    ]
    assert state.attributes.get(ATTR_MIN_TEMP) == 10
    assert state.attributes.get(ATTR_MAX_TEMP) == 30

    assert state.attributes.get(ATTR_TARGET_TEMP_STEP) == PRECISION_HALVES
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 19.00
