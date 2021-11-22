"""Tests for the WLED binary sensor platform."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import DEVICE_CLASS_UPDATE
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ENTITY_CATEGORY_DIAGNOSTIC,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_update_available(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the firmware update binary sensor."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.wled_rgb_light_firmware")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_UPDATE
    assert state.state == STATE_ON
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("binary_sensor.wled_rgb_light_firmware")
    assert entry
    assert entry.unique_id == "aabbccddeeff_update"
    assert entry.entity_category == ENTITY_CATEGORY_DIAGNOSTIC


@pytest.mark.parametrize("mock_wled", ["wled/rgb_websocket.json"], indirect=True)
async def test_no_update_available(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the update binary sensor. There is no update available."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.wled_websocket_firmware")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_UPDATE
    assert state.state == STATE_OFF
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("binary_sensor.wled_websocket_firmware")
    assert entry
    assert entry.unique_id == "aabbccddeeff_update"
    assert entry.entity_category == ENTITY_CATEGORY_DIAGNOSTIC
