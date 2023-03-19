"""Tests for the WLED sensor platform."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_wled")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the WLED sensors."""
    mock_config_entry.add_to_hass(hass)

    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.wled.sensor.utcnow", return_value=test_time):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfElectricCurrent.MILLIAMPERE
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert state.state == "470"

    assert (
        entry := entity_registry.async_get("sensor.wled_rgb_light_estimated_current")
    )
    assert entry.unique_id == "aabbccddeeff_estimated_current"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.wled_rgb_light_uptime"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-11-11T09:10:00+00:00"

    assert (entry := entity_registry.async_get("sensor.wled_rgb_light_uptime"))
    assert entry.unique_id == "aabbccddeeff_uptime"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.wled_rgb_light_free_memory"))
    assert state.attributes.get(ATTR_ICON) == "mdi:memory"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfInformation.BYTES
    assert state.state == "14600"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (entry := entity_registry.async_get("sensor.wled_rgb_light_free_memory"))
    assert entry.unique_id == "aabbccddeeff_free_heap"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.wled_rgb_light_wi_fi_signal"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "76"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (entry := entity_registry.async_get("sensor.wled_rgb_light_wi_fi_signal"))
    assert entry.unique_id == "aabbccddeeff_wifi_signal"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.wled_rgb_light_wi_fi_rssi"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SIGNAL_STRENGTH
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    assert state.state == "-62"

    assert (entry := entity_registry.async_get("sensor.wled_rgb_light_wi_fi_rssi"))
    assert entry.unique_id == "aabbccddeeff_wifi_rssi"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.wled_rgb_light_wi_fi_channel"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "11"

    assert (entry := entity_registry.async_get("sensor.wled_rgb_light_wi_fi_channel"))
    assert entry.unique_id == "aabbccddeeff_wifi_channel"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    assert (state := hass.states.get("sensor.wled_rgb_light_wi_fi_bssid"))
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "AA:AA:AA:AA:AA:BB"

    assert (entry := entity_registry.async_get("sensor.wled_rgb_light_wi_fi_bssid"))
    assert entry.unique_id == "aabbccddeeff_wifi_bssid"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.wled_rgb_light_uptime",
        "sensor.wled_rgb_light_free_memory",
        "sensor.wled_rgb_light_wi_fi_signal",
        "sensor.wled_rgb_light_wi_fi_rssi",
        "sensor.wled_rgb_light_wi_fi_channel",
        "sensor.wled_rgb_light_wi_fi_bssid",
    ),
)
@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default WLED sensors."""
    assert hass.states.get(entity_id) is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    "key",
    [
        "bssid",
        "channel",
        "rssi",
        "signal",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_wifi_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    key: str,
) -> None:
    """Test missing Wi-Fi information from WLED device."""
    # Remove Wi-Fi info
    device = mock_wled.update.return_value
    device.info.wifi = None

    # Setup
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(f"sensor.wled_rgb_light_wi_fi_{key}"))
    assert state.state == STATE_UNKNOWN


async def test_no_current_measurement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test missing current information when no max power is defined."""
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert hass.states.get("sensor.wled_rgb_light_estimated_current") is None
