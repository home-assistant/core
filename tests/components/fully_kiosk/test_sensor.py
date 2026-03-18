"""Test the Fully Kiosk Browser sensors."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from fullykiosk import FullyKioskError

from homeassistant.components.fully_kiosk.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensors_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk sensors."""
    state = hass.states.get("sensor.amazon_fire_battery")
    assert state
    assert state.state == "100"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Battery"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get("sensor.amazon_fire_battery")
    assert entry
    assert entry.unique_id == "abcdef-123456-batteryLevel"

    state = hass.states.get("sensor.amazon_fire_screen_orientation")
    assert state
    assert state.state == "90"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Screen orientation"

    entry = entity_registry.async_get("sensor.amazon_fire_screen_orientation")
    assert entry
    assert entry.unique_id == "abcdef-123456-screenOrientation"

    state = hass.states.get("sensor.amazon_fire_foreground_app")
    assert state
    assert state.state == "de.ozerov.fully"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Foreground app"

    entry = entity_registry.async_get("sensor.amazon_fire_foreground_app")
    assert entry
    assert entry.unique_id == "abcdef-123456-foregroundApp"

    state = hass.states.get("sensor.amazon_fire_current_page")
    assert state
    assert state.state == "https://homeassistant.local"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Current page"
    assert state.attributes.get("full_url") == "https://homeassistant.local"
    assert not state.attributes.get("truncated")

    entry = entity_registry.async_get("sensor.amazon_fire_current_page")
    assert entry
    assert entry.unique_id == "abcdef-123456-currentPage"

    state = hass.states.get("sensor.amazon_fire_internal_storage_free_space")
    assert state
    assert state.state == "11675.5"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_SIZE
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Amazon Fire Internal storage free space"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get("sensor.amazon_fire_internal_storage_free_space")
    assert entry
    assert entry.unique_id == "abcdef-123456-internalStorageFreeSpace"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.amazon_fire_internal_storage_total_space")
    assert state
    assert state.state == "12938.5"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_SIZE
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Amazon Fire Internal storage total space"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get("sensor.amazon_fire_internal_storage_total_space")
    assert entry
    assert entry.unique_id == "abcdef-123456-internalStorageTotalSpace"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.amazon_fire_free_memory")
    assert state
    assert state.state == "362.4"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_SIZE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Free memory"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get("sensor.amazon_fire_free_memory")
    assert entry
    assert entry.unique_id == "abcdef-123456-ramFreeMemory"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.amazon_fire_total_memory")
    assert state
    assert state.state == "1440.1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_SIZE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Amazon Fire Total memory"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get("sensor.amazon_fire_total_memory")
    assert entry
    assert entry.unique_id == "abcdef-123456-ramTotalMemory"
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
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.amazon_fire_internal_storage_free_space")
    assert state
    assert state.state == STATE_UNKNOWN

    # Test failed update
    mock_fully_kiosk.getDeviceInfo.side_effect = FullyKioskError("error", "status")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.amazon_fire_internal_storage_free_space")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_url_sensor_truncating(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that long URLs get truncated."""
    state = hass.states.get("sensor.amazon_fire_current_page")
    assert state
    assert state.state == "https://homeassistant.local"
    assert state.attributes.get("full_url") == "https://homeassistant.local"
    assert not state.attributes.get("truncated")

    long_url = "https://01234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789"
    assert len(long_url) > 256

    mock_fully_kiosk.getDeviceInfo.return_value = {
        "currentPage": long_url,
    }
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.amazon_fire_current_page")
    assert state
    assert state.state == long_url[0:255]
    assert state.attributes.get("full_url") == long_url
    assert state.attributes.get("truncated")
