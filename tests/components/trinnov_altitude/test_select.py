"""Tests for Trinnov Altitude select platform."""

import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_ID

from tests.common import MockConfigEntry

SOURCE_ENTITY_ID = f"select.trinnov_altitude_{MOCK_ID}_source"
PRESET_ENTITY_ID = f"select.trinnov_altitude_{MOCK_ID}_preset"
UPMIXER_ENTITY_ID = f"select.trinnov_altitude_{MOCK_ID}_upmixer"


async def test_entities(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test select entities are created."""
    assert hass.states.get(SOURCE_ENTITY_ID) is not None
    assert hass.states.get(PRESET_ENTITY_ID) is not None
    assert hass.states.get(UPMIXER_ENTITY_ID) is not None


async def test_source_select_option(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test source select service call."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SOURCE_ENTITY_ID, "option": "Apple TV"},
        blocking=True,
    )
    mock_device.source_set_by_name.assert_called_once_with("Apple TV")


async def test_preset_select_option(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test preset select service call."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PRESET_ENTITY_ID, "option": "Music"},
        blocking=True,
    )
    mock_device.preset_set.assert_called_once_with(1)


async def test_upmixer_select_option(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test upmixer select service call."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: UPMIXER_ENTITY_ID, "option": "dolby"},
        blocking=True,
    )
    assert mock_device.upmixer_set.call_count == 1


async def test_upmixer_select_option_invalid(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test invalid upmixer option raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError, match="Invalid upmixer mode"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: UPMIXER_ENTITY_ID, "option": "invalid_mode"},
            blocking=True,
        )
