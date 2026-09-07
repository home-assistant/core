"""Test the Govee BLE sensors."""

from datetime import timedelta
import time

import pytest

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.govee_ble.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.util import dt as dt_util

from . import (
    GV5140_SERVICE_INFO,
    GVH5075_SERVICE_INFO,
    GVH5106_SERVICE_INFO,
    GVH5178_PRIMARY_SERVICE_INFO,
    GVH5178_REMOTE_SERVICE_INFO,
    GVH5178_SERVICE_INFO_ERROR,
    GVH5184_SERVICE_INFO,
    GVH5198_SERVICE_INFO,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GVH5075_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.h5075_2762_temperature")
    temp_sensor_attribtes = temp_sensor.attributes
    assert temp_sensor.state == "21.3"
    assert temp_sensor_attribtes[ATTR_FRIENDLY_NAME] == "H5075 2762 Temperature"
    assert temp_sensor_attribtes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attribtes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_gvh5178_error(hass: HomeAssistant) -> None:
    """Test H5178 Remote in error marks state as unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:75:2B:C8",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GVH5178_SERVICE_INFO_ERROR)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.b51782bc8_remote_temperature")
    assert temp_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_gvh5178_multi_sensor(hass: HomeAssistant) -> None:
    """Test H5178 with a primary and remote sensor.

    The gateway sensor is responsible for broadcasting the state for
    all sensors and it does so in many advertisements. We want
    all the connected devices to stay available when the gateway
    sensor is available.
    """
    start_monotonic = time.monotonic()
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:75:2B:C8",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GVH5178_REMOTE_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.b51782bc8_remote_temperature")
    assert temp_sensor.state == "1.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.b51782bc8_remote_temperature")
    assert temp_sensor.state == STATE_UNAVAILABLE

    inject_bluetooth_service_info(hass, GVH5178_PRIMARY_SERVICE_INFO)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.b51782bc8_remote_temperature")
    assert temp_sensor.state == "1.0"

    primary_temp_sensor = hass.states.get("sensor.b51782bc8_primary_temperature")
    assert primary_temp_sensor.state == "1.0"

    # Fastforward time without BLE advertisements
    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.b51782bc8_remote_temperature")
    assert temp_sensor.state == STATE_UNAVAILABLE

    primary_temp_sensor = hass.states.get("sensor.b51782bc8_primary_temperature")
    assert primary_temp_sensor.state == STATE_UNAVAILABLE


async def test_gv5140(hass: HomeAssistant) -> None:
    """Test CO2, temperature and humidity sensors for a GV5140 device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GV5140_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.5140eeff_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "21.6"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "5140EEFF Temperature"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    humidity_sensor = hass.states.get("sensor.5140eeff_humidity")
    humidity_sensor_attributes = humidity_sensor.attributes
    assert humidity_sensor.state == "67.8"
    assert humidity_sensor_attributes[ATTR_FRIENDLY_NAME] == "5140EEFF Humidity"
    assert humidity_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humidity_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    co2_sensor = hass.states.get("sensor.5140eeff_carbon_dioxide")
    co2_sensor_attributes = co2_sensor.attributes
    assert co2_sensor.state == "531"
    assert co2_sensor_attributes[ATTR_FRIENDLY_NAME] == "5140EEFF Carbon dioxide"
    assert co2_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "ppm"
    assert co2_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("service_info", "expected_sensors"),
    [
        pytest.param(
            GVH5184_SERVICE_INFO,
            [
                (
                    "sensor.h5184_ac3d_temperature_probe_1",
                    "31.0",
                    "H5184 AC3D Temperature probe 1",
                ),
                (
                    "sensor.h5184_ac3d_temperature_alarm_probe_1",
                    "0.0",
                    "H5184 AC3D Temperature alarm probe 1",
                ),
                (
                    "sensor.h5184_ac3d_temperature_probe_2",
                    "28.0",
                    "H5184 AC3D Temperature probe 2",
                ),
                (
                    "sensor.h5184_ac3d_temperature_alarm_probe_2",
                    "0.0",
                    "H5184 AC3D Temperature alarm probe 2",
                ),
            ],
            id="h5184",
        ),
        pytest.param(
            GVH5198_SERVICE_INFO,
            [
                (
                    "sensor.h5198_ac3d_temperature_probe_3",
                    "36.0",
                    "H5198 AC3D Temperature probe 3",
                ),
                (
                    "sensor.h5198_ac3d_temperature_alarm_probe_3",
                    "0.0",
                    "H5198 AC3D Temperature alarm probe 3",
                ),
                (
                    "sensor.h5198_ac3d_low_temperature_alarm_probe_3",
                    "0.0",
                    "H5198 AC3D Low temperature alarm probe 3",
                ),
                (
                    "sensor.h5198_ac3d_temperature_probe_4",
                    "23.0",
                    "H5198 AC3D Temperature probe 4",
                ),
                (
                    "sensor.h5198_ac3d_temperature_alarm_probe_4",
                    "0.0",
                    "H5198 AC3D Temperature alarm probe 4",
                ),
                (
                    "sensor.h5198_ac3d_low_temperature_alarm_probe_4",
                    "0.0",
                    "H5198 AC3D Low temperature alarm probe 4",
                ),
            ],
            id="h5198",
        ),
    ],
)
async def test_probe_sensors(
    hass: HomeAssistant,
    service_info: BluetoothServiceInfo,
    expected_sensors: list[tuple[str, str, str]],
) -> None:
    """Test grill thermometer probe sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(expected_sensors)

    for entity_id, state, friendly_name in expected_sensors:
        sensor = hass.states.get(entity_id)
        assert sensor.state == state
        assert sensor.attributes[ATTR_FRIENDLY_NAME] == friendly_name

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_gvh5106(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors for a device with PM25."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="CC:32:37:35:4E:05",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GVH5106_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    pm25_sensor = hass.states.get("sensor.h5106_4e05_pm2_5")
    pm25_sensor_attributes = pm25_sensor.attributes
    assert pm25_sensor.state == "0"
    assert pm25_sensor_attributes[ATTR_FRIENDLY_NAME] == "H5106 4E05 PM2.5"
    assert pm25_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "μg/m³"
    assert pm25_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
