"""Test zha fan."""
import pytest
import zigpy.profiles.zha as zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.hvac as hvac

from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_SPEED,
    DOMAIN,
    SERVICE_SET_SPEED,
    SPEED_HIGH,
    SPEED_MEDIUM,
    SPEED_OFF,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.zha.core.discovery import GROUP_PROBE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from .common import (
    async_enable_traffic,
    async_find_group_entity_id,
    async_test_rejoin,
    find_entity_id,
    get_zha_gateway,
    send_attributes_report,
)

from tests.async_mock import call

IEEE_GROUPABLE_DEVICE = "01:2d:6f:00:0a:90:69:e8"
IEEE_GROUPABLE_DEVICE2 = "02:2d:6f:00:0a:90:69:e8"


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""
    endpoints = {
        1: {"in_clusters": [hvac.Fan.cluster_id], "out_clusters": [], "device_type": 0}
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
async def coordinator(hass, zigpy_device_mock, zha_device_joined):
    """Test zha fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [],
                "out_clusters": [],
                "device_type": zha.DeviceType.COLOR_DIMMABLE_LIGHT,
            }
        },
        ieee="00:15:8d:00:02:32:4f:32",
        nwk=0x0000,
        node_descriptor=b"\xf8\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff",
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.set_available(True)
    return zha_device


@pytest.fixture
async def device_fan_1(hass, zigpy_device_mock, zha_device_joined):
    """Test zha fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.OnOff.cluster_id, hvac.Fan.cluster_id],
                "out_clusters": [],
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.set_available(True)
    return zha_device


@pytest.fixture
async def device_fan_2(hass, zigpy_device_mock, zha_device_joined):
    """Test zha fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [
                    general.OnOff.cluster_id,
                    hvac.Fan.cluster_id,
                    general.LevelControl.cluster_id,
                ],
                "out_clusters": [],
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE2,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.set_available(True)
    return zha_device


async def test_fan(hass, zha_device_joined_restored, zigpy_device):
    """Test zha fan platform."""

    zha_device = await zha_device_joined_restored(zigpy_device)
    cluster = zigpy_device.endpoints.get(1).fan
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the fan was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at fan
    await send_attributes_report(hass, cluster, {1: 2, 0: 1, 2: 3})
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at fan
    await send_attributes_report(hass, cluster, {1: 1, 0: 0, 2: 2})
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    cluster.write_attributes.reset_mock()
    await async_turn_on(hass, entity_id)
    assert len(cluster.write_attributes.mock_calls) == 1
    assert cluster.write_attributes.call_args == call({"fan_mode": 2})

    # turn off from HA
    cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert len(cluster.write_attributes.mock_calls) == 1
    assert cluster.write_attributes.call_args == call({"fan_mode": 0})

    # change speed from HA
    cluster.write_attributes.reset_mock()
    await async_set_speed(hass, entity_id, speed=fan.SPEED_HIGH)
    assert len(cluster.write_attributes.mock_calls) == 1
    assert cluster.write_attributes.call_args == call({"fan_mode": 3})

    # test adding new fan to the network and HA
    await async_test_rejoin(hass, zigpy_device, [cluster], (1,))


async def async_turn_on(hass, entity_id, speed=None):
    """Turn fan on."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_SPEED, speed)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id):
    """Turn fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


async def async_set_speed(hass, entity_id, speed=None):
    """Set speed for specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_SPEED, speed)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_SPEED, data, blocking=True)


async def async_test_zha_group_fan_entity(
    hass, device_fan_1, device_fan_2, coordinator
):
    """Test the fan entity for a ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    assert zha_gateway is not None
    zha_gateway.coordinator_zha_device = coordinator
    coordinator._zha_gateway = zha_gateway
    device_fan_1._zha_gateway = zha_gateway
    device_fan_2._zha_gateway = zha_gateway
    member_ieee_addresses = [device_fan_1.ieee, device_fan_2.ieee]

    # test creating a group with 2 members
    zha_group = await zha_gateway.async_create_zigpy_group(
        "Test Group", member_ieee_addresses
    )
    await hass.async_block_till_done()

    assert zha_group is not None
    assert len(zha_group.members) == 2
    for member in zha_group.members:
        assert member.ieee in member_ieee_addresses

    entity_domains = GROUP_PROBE.determine_entity_domains(zha_group)
    assert len(entity_domains) == 2

    assert LIGHT_DOMAIN in entity_domains
    assert DOMAIN in entity_domains

    entity_id = async_find_group_entity_id(hass, DOMAIN, zha_group)
    assert hass.states.get(entity_id) is not None

    group_fan_cluster = zha_group.endpoint[hvac.Fan.cluster_id]
    dev1_fan_cluster = device_fan_1.endpoints[1].fan
    dev2_fan_cluster = device_fan_2.endpoints[1].fan

    # test that the lights were created and that they are unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_group.members)

    # test that the fan group entity was created and is off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_turn_on(hass, entity_id)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args == call({"fan_mode": 2})
    assert hass.states.get(entity_id).state == SPEED_MEDIUM

    # turn off from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args == call({"fan_mode": 0})
    assert hass.states.get(entity_id).state == STATE_OFF

    # change speed from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_set_speed(hass, entity_id, speed=fan.SPEED_HIGH)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args == call({"fan_mode": 3})
    assert hass.states.get(entity_id).state == SPEED_HIGH

    # test some of the group logic to make sure we key off states correctly
    await dev1_fan_cluster.async_set_speed(SPEED_OFF)
    await dev2_fan_cluster.async_set_speed(SPEED_OFF)

    # test that group fan is off
    assert hass.states.get(entity_id).state == STATE_OFF

    await dev1_fan_cluster.async_set_speed(SPEED_MEDIUM)

    # test that group fan is speed medium
    assert hass.states.get(entity_id).state == SPEED_MEDIUM

    await dev1_fan_cluster.async_set_speed(SPEED_OFF)

    # test that group fan is now off
    assert hass.states.get(entity_id).state == STATE_OFF
