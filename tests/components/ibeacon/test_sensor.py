"""Test the ibeacon sensors."""
from datetime import timedelta

import pytest

from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.ibeacon.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import (
    BLUECHARM_BEACON_SERVICE_INFO,
    BLUECHARM_BEACON_SERVICE_INFO_2,
    BLUECHARM_BLE_DEVICE,
    FEASY_BEACON_BLE_DEVICE,
    FEASY_BEACON_SERVICE_INFO_1,
    FEASY_BEACON_SERVICE_INFO_2,
    NO_NAME_BEACON_SERVICE_INFO,
    bluetooth_service_info_replace as replace,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


async def test_sensors_updates_fixed_mac_address(hass: HomeAssistant) -> None:
    """Test creating and updating sensors with a fixed mac address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch_all_discovered_devices([BLUECHARM_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_8105_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "2"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME]
        == "BlueCharm_177999 8105 Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    with patch_all_discovered_devices([BLUECHARM_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO_2)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_8105_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "0"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME]
        == "BlueCharm_177999 8105 Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    # Make sure RSSI updates are picked up by the periodic update
    inject_bluetooth_service_info(
        hass, replace(BLUECHARM_BEACON_SERVICE_INFO_2, rssi=-84)
    )

    # We should not see it right away since the update interval is 60 seconds
    distance_sensor = hass.states.get("sensor.bluecharm_177999_8105_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "0"

    with patch_all_discovered_devices([BLUECHARM_BLE_DEVICE]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL.total_seconds() * 2),
        )
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_8105_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "14"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME]
        == "BlueCharm_177999 8105 Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    with patch_all_discovered_devices([]):
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS * 2)
        )
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_8105_estimated_distance")
    assert distance_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensor_with_no_local_name(hass: HomeAssistant) -> None:
    """Test creating and updating sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, NO_NAME_BEACON_SERVICE_INFO)
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "sensor.4e6f4e61_6d65_6172_6d42_6561636f6e73_3838_4949_8105_estimated_distance"
        )
        is not None
    )

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_sensor_sees_last_service_info(hass: HomeAssistant) -> None:
    """Test sensors are created from recent history."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance").state == "2"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_can_unload_and_reload(hass: HomeAssistant) -> None:
    """Test sensors get recreated on unload/setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance").state == "2"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance").state
        == STATE_UNAVAILABLE
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance").state == "2"
    )


async def test_multiple_uuids_same_beacon(hass: HomeAssistant) -> None:
    """Test a beacon that broadcasts multiple uuids."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch_all_discovered_devices([FEASY_BEACON_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, FEASY_BEACON_SERVICE_INFO_1)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.fsc_bp108_eeff_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "400"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME] == "FSC-BP108 EEFF Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    with patch_all_discovered_devices([FEASY_BEACON_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, FEASY_BEACON_SERVICE_INFO_2)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.fsc_bp108_eeff_estimated_distance_2")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "0"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME] == "FSC-BP108 EEFF Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    with patch_all_discovered_devices([FEASY_BEACON_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, FEASY_BEACON_SERVICE_INFO_1)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.fsc_bp108_eeff_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "400"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME] == "FSC-BP108 EEFF Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    distance_sensor = hass.states.get("sensor.fsc_bp108_eeff_estimated_distance_2")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "0"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME] == "FSC-BP108 EEFF Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"
