"""Tests for Fritz!Tools sensor platform."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fritzconnection.core.exceptions import FritzConnectionException

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.fritz.sensor import SENSOR_TYPES
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed

SENSOR_STATES: dict[str, dict[str, Any]] = {
    "sensor.mock_title_external_ip": {
        ATTR_STATE: "1.2.3.4",
        ATTR_ICON: "mdi:earth",
    },
    "sensor.mock_title_external_ipv6": {
        ATTR_STATE: "fec0::1",
        ATTR_ICON: "mdi:earth",
    },
    "sensor.mock_title_device_uptime": {
        # ATTR_STATE: "2022-02-05T17:46:04+00:00",
        ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP,
    },
    "sensor.mock_title_connection_uptime": {
        # ATTR_STATE: "2022-03-06T11:27:16+00:00",
        ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP,
    },
    "sensor.mock_title_upload_throughput": {
        ATTR_STATE: "3.4",
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_UNIT_OF_MEASUREMENT: "kB/s",
        ATTR_ICON: "mdi:upload",
    },
    "sensor.mock_title_download_throughput": {
        ATTR_STATE: "67.6",
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_UNIT_OF_MEASUREMENT: "kB/s",
        ATTR_ICON: "mdi:download",
    },
    "sensor.mock_title_max_connection_upload_throughput": {
        ATTR_STATE: "2105.0",
        ATTR_UNIT_OF_MEASUREMENT: "kbit/s",
        ATTR_ICON: "mdi:upload",
    },
    "sensor.mock_title_max_connection_download_throughput": {
        ATTR_STATE: "10087.0",
        ATTR_UNIT_OF_MEASUREMENT: "kbit/s",
        ATTR_ICON: "mdi:download",
    },
    "sensor.mock_title_gb_sent": {
        ATTR_STATE: "1.7",
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        ATTR_UNIT_OF_MEASUREMENT: "GB",
        ATTR_ICON: "mdi:upload",
    },
    "sensor.mock_title_gb_received": {
        ATTR_STATE: "5.2",
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        ATTR_UNIT_OF_MEASUREMENT: "GB",
        ATTR_ICON: "mdi:download",
    },
    "sensor.mock_title_link_upload_throughput": {
        ATTR_STATE: "51805.0",
        ATTR_UNIT_OF_MEASUREMENT: "kbit/s",
        ATTR_ICON: "mdi:upload",
    },
    "sensor.mock_title_link_download_throughput": {
        ATTR_STATE: "318557.0",
        ATTR_UNIT_OF_MEASUREMENT: "kbit/s",
        ATTR_ICON: "mdi:download",
    },
    "sensor.mock_title_link_upload_noise_margin": {
        ATTR_STATE: "9.0",
        ATTR_UNIT_OF_MEASUREMENT: "dB",
        ATTR_ICON: "mdi:upload",
    },
    "sensor.mock_title_link_download_noise_margin": {
        ATTR_STATE: "8.0",
        ATTR_UNIT_OF_MEASUREMENT: "dB",
        ATTR_ICON: "mdi:download",
    },
    "sensor.mock_title_link_upload_power_attenuation": {
        ATTR_STATE: "7.0",
        ATTR_UNIT_OF_MEASUREMENT: "dB",
        ATTR_ICON: "mdi:upload",
    },
    "sensor.mock_title_link_download_power_attenuation": {
        ATTR_STATE: "12.0",
        ATTR_UNIT_OF_MEASUREMENT: "dB",
        ATTR_ICON: "mdi:download",
    },
}


async def test_sensor_setup(hass: HomeAssistant, fc_class_mock, fh_class_mock) -> None:
    """Test setup of Fritz!Tools sesnors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    sensors = hass.states.async_all(SENSOR_DOMAIN)
    assert len(sensors) == len(SENSOR_TYPES)

    for sensor in sensors:
        assert SENSOR_STATES.get(sensor.entity_id) is not None
        for key, val in SENSOR_STATES[sensor.entity_id].items():
            if key == ATTR_STATE:
                assert sensor.state == val
            else:
                assert sensor.attributes.get(key) == val


async def test_sensor_update_fail(
    hass: HomeAssistant, fc_class_mock, fh_class_mock
) -> None:
    """Test failed update of Fritz!Tools sesnors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    fc_class_mock().call_action_side_effect(FritzConnectionException)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=300))
    await hass.async_block_till_done()

    sensors = hass.states.async_all(SENSOR_DOMAIN)
    for sensor in sensors:
        assert sensor.state == STATE_UNAVAILABLE
