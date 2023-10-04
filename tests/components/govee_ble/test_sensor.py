"""Test the Govee BLE sensors."""
from datetime import timedelta
import time
from unittest.mock import patch

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
from homeassistant.util import dt as dt_util

from . import (
    GVH5075_SERVICE_INFO,
    GVH5178_PRIMARY_SERVICE_INFO,
    GVH5178_REMOTE_SERVICE_INFO,
    GVH5178_SERVICE_INFO_ERROR,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
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

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
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
    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
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
