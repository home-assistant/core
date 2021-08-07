"""Tests for the WLED sensor platform."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TIMESTAMP,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.components.wled.const import ATTR_LED_COUNT, ATTR_MAX_POWER, DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DATA_BYTES,
    ELECTRIC_CURRENT_MILLIAMPERE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test the creation and values of the WLED sensors."""
    registry = er.async_get(hass)

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_uptime",
        suggested_object_id="wled_rgb_light_uptime",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_free_heap",
        suggested_object_id="wled_rgb_light_free_memory",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_wifi_signal",
        suggested_object_id="wled_rgb_light_wifi_signal",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_wifi_rssi",
        suggested_object_id="wled_rgb_light_wifi_rssi",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_wifi_channel",
        suggested_object_id="wled_rgb_light_wifi_channel",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_wifi_bssid",
        suggested_object_id="wled_rgb_light_wifi_bssid",
        disabled_by=None,
    )

    # Setup
    mock_config_entry.add_to_hass(hass)
    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.wled.sensor.utcnow", return_value=test_time):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.wled_rgb_light_estimated_current")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:power"
    assert state.attributes.get(ATTR_LED_COUNT) == 30
    assert state.attributes.get(ATTR_MAX_POWER) == 850
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ELECTRIC_CURRENT_MILLIAMPERE
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_CURRENT
    assert state.state == "470"

    entry = registry.async_get("sensor.wled_rgb_light_estimated_current")
    assert entry
    assert entry.unique_id == "aabbccddeeff_estimated_current"

    state = hass.states.get("sensor.wled_rgb_light_uptime")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TIMESTAMP
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-11-11T09:10:00+00:00"

    entry = registry.async_get("sensor.wled_rgb_light_uptime")
    assert entry
    assert entry.unique_id == "aabbccddeeff_uptime"

    state = hass.states.get("sensor.wled_rgb_light_free_memory")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:memory"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == DATA_BYTES
    assert state.state == "14600"

    entry = registry.async_get("sensor.wled_rgb_light_free_memory")
    assert entry
    assert entry.unique_id == "aabbccddeeff_free_heap"

    state = hass.states.get("sensor.wled_rgb_light_wifi_signal")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "76"

    entry = registry.async_get("sensor.wled_rgb_light_wifi_signal")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_signal"

    state = hass.states.get("sensor.wled_rgb_light_wifi_rssi")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_SIGNAL_STRENGTH
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    assert state.state == "-62"

    entry = registry.async_get("sensor.wled_rgb_light_wifi_rssi")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_rssi"

    state = hass.states.get("sensor.wled_rgb_light_wifi_channel")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "11"

    entry = registry.async_get("sensor.wled_rgb_light_wifi_channel")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_channel"

    state = hass.states.get("sensor.wled_rgb_light_wifi_bssid")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "AA:AA:AA:AA:AA:BB"

    entry = registry.async_get("sensor.wled_rgb_light_wifi_bssid")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_bssid"


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
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Test the disabled by default WLED sensors."""
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION


@pytest.mark.parametrize(
    "key",
    [
        "bssid",
        "channel",
        "rssi",
        "signal",
    ],
)
async def test_no_wifi_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    key: str,
) -> None:
    """Test missing Wi-Fi information from WLED device."""
    registry = er.async_get(hass)

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"aabbccddeeff_wifi_{key}",
        suggested_object_id=f"wled_rgb_light_wifi_{key}",
        disabled_by=None,
    )

    # Remove Wi-Fi info
    device = mock_wled.update.return_value
    device.info.wifi = None

    # Setup
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.wled_rgb_light_wifi_{key}")
    assert state
    assert state.state == STATE_UNKNOWN
