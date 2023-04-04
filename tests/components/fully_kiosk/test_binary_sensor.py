"""Test the Fully Kiosk Browser binary sensors."""
from unittest.mock import MagicMock

from fullykiosk import FullyKioskError

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.fully_kiosk.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk binary sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("binary_sensor.amazon_fire_plugged_in")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PLUG
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Plugged in"

    entry = entity_registry.async_get("binary_sensor.amazon_fire_plugged_in")
    assert entry
    assert entry.unique_id == "abcdef-123456-plugged"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("binary_sensor.amazon_fire_kiosk_mode")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Kiosk mode"

    entry = entity_registry.async_get("binary_sensor.amazon_fire_kiosk_mode")
    assert entry
    assert entry.unique_id == "abcdef-123456-kioskMode"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("binary_sensor.amazon_fire_device_admin")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Device admin"

    entry = entity_registry.async_get("binary_sensor.amazon_fire_device_admin")
    assert entry
    assert entry.unique_id == "abcdef-123456-isDeviceAdmin"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url == "http://192.168.1.234:2323"
    assert device_entry.entry_type is None
    assert device_entry.hw_version is None
    assert device_entry.identifiers == {(DOMAIN, "abcdef-123456")}
    assert device_entry.manufacturer == "amzn"
    assert device_entry.model == "KFDOWI"
    assert device_entry.name == "Amazon Fire"
    assert device_entry.sw_version == "1.42.5"

    # Test unknown/missing data
    mock_fully_kiosk.getDeviceInfo.return_value = {}
    async_fire_time_changed(hass, dt.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.amazon_fire_plugged_in")
    assert state
    assert state.state == STATE_UNKNOWN

    # Test failed update
    mock_fully_kiosk.getDeviceInfo.side_effect = FullyKioskError("error", "status")
    async_fire_time_changed(hass, dt.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.amazon_fire_plugged_in")
    assert state
    assert state.state == STATE_UNAVAILABLE
