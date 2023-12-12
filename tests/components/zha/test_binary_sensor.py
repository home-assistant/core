"""Test ZHA binary sensor."""
from unittest.mock import patch

import pytest
import zigpy.profiles.zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.measurement as measurement
import zigpy.zcl.clusters.security as security

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    send_attributes_report,
    update_attribute_cache,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import async_mock_load_restore_state_from_storage

DEVICE_IAS = {
    1: {
        SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
        SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.IAS_ZONE,
        SIG_EP_INPUT: [security.IasZone.cluster_id],
        SIG_EP_OUTPUT: [],
    }
}


DEVICE_OCCUPANCY = {
    1: {
        SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
        SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.OCCUPANCY_SENSOR,
        SIG_EP_INPUT: [measurement.OccupancySensing.cluster_id],
        SIG_EP_OUTPUT: [],
    }
}


DEVICE_ONOFF = {
    1: {
        SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
        SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SENSOR,
        SIG_EP_INPUT: [],
        SIG_EP_OUTPUT: [general.OnOff.cluster_id],
    }
}


@pytest.fixture(autouse=True)
def binary_sensor_platform_only():
    """Only set up the binary_sensor and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SELECT,
        ),
    ):
        yield


async def async_test_binary_sensor_on_off(hass, cluster, entity_id):
    """Test getting on and off messages for binary sensors."""
    # binary sensor on
    await send_attributes_report(hass, cluster, {1: 0, 0: 1, 2: 2})
    assert hass.states.get(entity_id).state == STATE_ON

    # binary sensor off
    await send_attributes_report(hass, cluster, {1: 1, 0: 0, 2: 2})
    assert hass.states.get(entity_id).state == STATE_OFF


async def async_test_iaszone_on_off(hass, cluster, entity_id):
    """Test getting on and off messages for iaszone binary sensors."""
    # binary sensor on
    cluster.listener_event("cluster_command", 1, 0, [1])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # binary sensor off
    cluster.listener_event("cluster_command", 1, 0, [0])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # check that binary sensor remains off when non-alarm bits change
    cluster.listener_event("cluster_command", 1, 0, [0b1111111100])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    ("device", "on_off_test", "cluster_name", "reporting", "name"),
    [
        (
            DEVICE_IAS,
            async_test_iaszone_on_off,
            "ias_zone",
            (0,),
            "FakeManufacturer FakeModel IAS zone",
        ),
        (
            DEVICE_OCCUPANCY,
            async_test_binary_sensor_on_off,
            "occupancy",
            (1,),
            "FakeManufacturer FakeModel Occupancy",
        ),
    ],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    zigpy_device_mock,
    zha_device_joined_restored,
    device,
    on_off_test,
    cluster_name,
    reporting,
    name,
) -> None:
    """Test ZHA binary_sensor platform."""
    zigpy_device = zigpy_device_mock(device)
    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = find_entity_id(Platform.BINARY_SENSOR, zha_device, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).name == name
    assert hass.states.get(entity_id).state == STATE_OFF
    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the sensors exist and are in the unavailable state
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await async_enable_traffic(hass, [zha_device])

    # test that the sensors exist and are in the off state
    assert hass.states.get(entity_id).state == STATE_OFF

    # test getting messages that trigger and reset the sensors
    cluster = getattr(zigpy_device.endpoints[1], cluster_name)
    await on_off_test(hass, cluster, entity_id)

    # test rejoin
    await async_test_rejoin(hass, zigpy_device, [cluster], reporting)
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "restored_state",
    [
        STATE_ON,
        STATE_OFF,
    ],
)
async def test_binary_sensor_migration_not_migrated(
    hass: HomeAssistant,
    zigpy_device_mock,
    core_rs,
    zha_device_restored,
    restored_state,
) -> None:
    """Test temporary ZHA IasZone binary_sensor migration to zigpy cache."""

    entity_id = "binary_sensor.fakemanufacturer_fakemodel_ias_zone"
    core_rs(entity_id, state=restored_state, attributes={})  # migration sensor state
    await async_mock_load_restore_state_from_storage(hass)

    zigpy_device = zigpy_device_mock(DEVICE_IAS)

    zha_device = await zha_device_restored(zigpy_device)
    entity_id = find_entity_id(Platform.BINARY_SENSOR, zha_device, hass)

    assert entity_id is not None
    assert hass.states.get(entity_id).state == restored_state

    # confirm migration extra state attribute was set to True
    assert hass.states.get(entity_id).attributes["migrated_to_cache"]


async def test_binary_sensor_migration_already_migrated(
    hass: HomeAssistant,
    zigpy_device_mock,
    core_rs,
    zha_device_restored,
) -> None:
    """Test temporary ZHA IasZone binary_sensor migration doesn't migrate multiple times."""

    entity_id = "binary_sensor.fakemanufacturer_fakemodel_ias_zone"
    core_rs(entity_id, state=STATE_OFF, attributes={"migrated_to_cache": True})
    await async_mock_load_restore_state_from_storage(hass)

    zigpy_device = zigpy_device_mock(DEVICE_IAS)

    cluster = zigpy_device.endpoints.get(1).ias_zone
    cluster.PLUGGED_ATTR_READS = {
        "zone_status": security.IasZone.ZoneStatus.Alarm_1,
    }
    update_attribute_cache(cluster)

    zha_device = await zha_device_restored(zigpy_device)
    entity_id = find_entity_id(Platform.BINARY_SENSOR, zha_device, hass)

    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_ON  # matches attribute cache
    assert hass.states.get(entity_id).attributes["migrated_to_cache"]


@pytest.mark.parametrize(
    "restored_state",
    [
        STATE_ON,
        STATE_OFF,
    ],
)
async def test_onoff_binary_sensor_restore_state(
    hass: HomeAssistant,
    zigpy_device_mock,
    core_rs,
    zha_device_restored,
    restored_state,
) -> None:
    """Test ZHA OnOff binary_sensor restores last state from HA."""

    entity_id = "binary_sensor.fakemanufacturer_fakemodel_opening"
    core_rs(entity_id, state=restored_state, attributes={})
    await async_mock_load_restore_state_from_storage(hass)

    zigpy_device = zigpy_device_mock(DEVICE_ONOFF)
    zha_device = await zha_device_restored(zigpy_device)
    entity_id = find_entity_id(Platform.BINARY_SENSOR, zha_device, hass)

    assert entity_id is not None
    assert hass.states.get(entity_id).state == restored_state
