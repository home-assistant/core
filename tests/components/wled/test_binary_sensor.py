"""Tests for the WLED binary sensor platform."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry


async def test_update_available(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the firmware update binary sensor."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.wled_rgb_light_firmware")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.UPDATE
    assert state.state == STATE_ON
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("binary_sensor.wled_rgb_light_firmware")
    assert entry
    assert entry.unique_id == "aabbccddeeff_update"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize("mock_wled", ["wled/rgb_websocket.json"], indirect=True)
async def test_no_update_available(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the update binary sensor. There is no update available."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.wled_websocket_firmware")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.UPDATE
    assert state.state == STATE_OFF
    assert ATTR_ICON not in state.attributes

    entry = entity_registry.async_get("binary_sensor.wled_websocket_firmware")
    assert entry
    assert entry.unique_id == "aabbccddeeff_update"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the binary update sensor is disabled by default."""
    registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.wled_rgb_light_firmware")
    assert state is None

    entry = registry.async_get("binary_sensor.wled_rgb_light_firmware")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
