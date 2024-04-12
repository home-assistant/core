"""Test ZHA fan."""

from unittest.mock import AsyncMock, call, patch

import pytest
import zhaquirks.ikea.starkvind
from zigpy.device import Device
from zigpy.exceptions import ZigbeeException
from zigpy.profiles import zha
from zigpy.zcl.clusters import general, hvac
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    NotValidPresetModeError,
)
from homeassistant.components.zha.core.device import ZHADevice
from homeassistant.components.zha.core.discovery import GROUP_PROBE
from homeassistant.components.zha.core.group import GroupMember
from homeassistant.components.zha.core.helpers import get_zha_gateway
from homeassistant.components.zha.fan import (
    PRESET_MODE_AUTO,
    PRESET_MODE_ON,
    PRESET_MODE_SMART,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import (
    async_enable_traffic,
    async_find_group_entity_id,
    async_test_rejoin,
    async_wait_for_updates,
    find_entity_id,
    send_attributes_report,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

IEEE_GROUPABLE_DEVICE = "01:2d:6f:00:0a:90:69:e8"
IEEE_GROUPABLE_DEVICE2 = "02:2d:6f:00:0a:90:69:e8"


@pytest.fixture(autouse=True)
def fan_platform_only():
    """Only set up the fan and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BUTTON,
            Platform.BINARY_SENSOR,
            Platform.FAN,
            Platform.LIGHT,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
        ),
    ):
        yield


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Fan zigpy device."""
    endpoints = {
        1: {
            SIG_EP_INPUT: [hvac.Fan.cluster_id],
            SIG_EP_OUTPUT: [],
            SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
            SIG_EP_PROFILE: zha.PROFILE_ID,
        }
    }
    return zigpy_device_mock(
        endpoints, node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00"
    )


@pytest.fixture
async def coordinator(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Groups.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="00:15:8d:00:02:32:4f:32",
        nwk=0x0000,
        node_descriptor=b"\xf8\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff",
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


@pytest.fixture
async def device_fan_1(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Groups.cluster_id,
                    general.OnOff.cluster_id,
                    hvac.Fan.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            },
        },
        ieee=IEEE_GROUPABLE_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    await hass.async_block_till_done()
    return zha_device


@pytest.fixture
async def device_fan_2(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Groups.cluster_id,
                    general.OnOff.cluster_id,
                    hvac.Fan.cluster_id,
                    general.LevelControl.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            },
        },
        ieee=IEEE_GROUPABLE_DEVICE2,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    await hass.async_block_till_done()
    return zha_device


async def test_fan(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device
) -> None:
    """Test ZHA fan platform."""

    zha_device = await zha_device_joined_restored(zigpy_device)
    cluster = zigpy_device.endpoints.get(1).fan
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF
    await async_enable_traffic(hass, [zha_device], enabled=False)
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
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 2}, manufacturer=None)
    ]

    # turn off from HA
    cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 0}, manufacturer=None)
    ]

    # change speed from HA
    cluster.write_attributes.reset_mock()
    await async_set_percentage(hass, entity_id, percentage=100)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 3}, manufacturer=None)
    ]

    # change preset_mode from HA
    cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_ON)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 4}, manufacturer=None)
    ]

    # set invalid preset_mode from HA
    cluster.write_attributes.reset_mock()
    with pytest.raises(NotValidPresetModeError) as exc:
        await async_set_preset_mode(
            hass, entity_id, preset_mode="invalid does not exist"
        )
    assert exc.value.translation_key == "not_valid_preset_mode"
    assert len(cluster.write_attributes.mock_calls) == 0

    # test adding new fan to the network and HA
    await async_test_rejoin(hass, zigpy_device, [cluster], (1,))


async def async_turn_on(hass, entity_id, percentage=None):
    """Turn fan on."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_PERCENTAGE, percentage)]
        if value is not None
    }

    await hass.services.async_call(Platform.FAN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id):
    """Turn fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(Platform.FAN, SERVICE_TURN_OFF, data, blocking=True)


async def async_set_percentage(hass, entity_id, percentage=None):
    """Set percentage for specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_PERCENTAGE, percentage)]
        if value is not None
    }

    await hass.services.async_call(
        Platform.FAN, SERVICE_SET_PERCENTAGE, data, blocking=True
    )


async def async_set_preset_mode(hass, entity_id, preset_mode=None):
    """Set preset_mode for specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_PRESET_MODE, preset_mode)]
        if value is not None
    }

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_SET_PRESET_MODE, data, blocking=True
    )


@patch(
    "zigpy.zcl.clusters.hvac.Fan.write_attributes",
    new=AsyncMock(return_value=zcl_f.WriteAttributesResponse.deserialize(b"\x00")[0]),
)
@patch(
    "homeassistant.components.zha.entity.DEFAULT_UPDATE_GROUP_FROM_CHILD_DELAY",
    new=0,
)
async def test_zha_group_fan_entity(
    hass: HomeAssistant, device_fan_1, device_fan_2, coordinator
) -> None:
    """Test the fan entity for a ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    assert zha_gateway is not None
    zha_gateway.coordinator_zha_device = coordinator
    coordinator._zha_gateway = zha_gateway
    device_fan_1._zha_gateway = zha_gateway
    device_fan_2._zha_gateway = zha_gateway
    member_ieee_addresses = [device_fan_1.ieee, device_fan_2.ieee]
    members = [GroupMember(device_fan_1.ieee, 1), GroupMember(device_fan_2.ieee, 1)]

    # test creating a group with 2 members
    zha_group = await zha_gateway.async_create_zigpy_group("Test Group", members)
    await hass.async_block_till_done()

    assert zha_group is not None
    assert len(zha_group.members) == 2
    for member in zha_group.members:
        assert member.device.ieee in member_ieee_addresses
        assert member.group == zha_group
        assert member.endpoint is not None

    entity_domains = GROUP_PROBE.determine_entity_domains(hass, zha_group)
    assert len(entity_domains) == 2

    assert Platform.LIGHT in entity_domains
    assert Platform.FAN in entity_domains

    entity_id = async_find_group_entity_id(hass, Platform.FAN, zha_group)
    assert hass.states.get(entity_id) is not None

    group_fan_cluster = zha_group.endpoint[hvac.Fan.cluster_id]

    dev1_fan_cluster = device_fan_1.device.endpoints[1].fan
    dev2_fan_cluster = device_fan_2.device.endpoints[1].fan

    await async_enable_traffic(hass, [device_fan_1, device_fan_2], enabled=False)
    await async_wait_for_updates(hass)
    # test that the fans were created and that they are unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [device_fan_1, device_fan_2])
    await async_wait_for_updates(hass)
    # test that the fan group entity was created and is off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_turn_on(hass, entity_id)
    await hass.async_block_till_done()
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 2}

    # turn off from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 0}

    # change speed from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_set_percentage(hass, entity_id, percentage=100)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 3}

    # change preset mode from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_ON)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 4}

    # change preset mode from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_AUTO)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 5}

    # change preset mode from HA
    group_fan_cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_SMART)
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 6}

    # test some of the group logic to make sure we key off states correctly
    await send_attributes_report(hass, dev1_fan_cluster, {0: 0})
    await send_attributes_report(hass, dev2_fan_cluster, {0: 0})
    await hass.async_block_till_done()

    # test that group fan is off
    assert hass.states.get(entity_id).state == STATE_OFF

    await send_attributes_report(hass, dev2_fan_cluster, {0: 2})
    await async_wait_for_updates(hass)

    # test that group fan is speed medium
    assert hass.states.get(entity_id).state == STATE_ON

    await send_attributes_report(hass, dev2_fan_cluster, {0: 0})
    await async_wait_for_updates(hass)

    # test that group fan is now off
    assert hass.states.get(entity_id).state == STATE_OFF


@patch(
    "zigpy.zcl.clusters.hvac.Fan.write_attributes",
    new=AsyncMock(side_effect=ZigbeeException),
)
@patch(
    "homeassistant.components.zha.entity.DEFAULT_UPDATE_GROUP_FROM_CHILD_DELAY",
    new=0,
)
async def test_zha_group_fan_entity_failure_state(
    hass: HomeAssistant,
    device_fan_1,
    device_fan_2,
    coordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the fan entity for a ZHA group when writing attributes generates an exception."""
    zha_gateway = get_zha_gateway(hass)
    assert zha_gateway is not None
    zha_gateway.coordinator_zha_device = coordinator
    coordinator._zha_gateway = zha_gateway
    device_fan_1._zha_gateway = zha_gateway
    device_fan_2._zha_gateway = zha_gateway
    member_ieee_addresses = [device_fan_1.ieee, device_fan_2.ieee]
    members = [GroupMember(device_fan_1.ieee, 1), GroupMember(device_fan_2.ieee, 1)]

    # test creating a group with 2 members
    zha_group = await zha_gateway.async_create_zigpy_group("Test Group", members)
    await hass.async_block_till_done()

    assert zha_group is not None
    assert len(zha_group.members) == 2
    for member in zha_group.members:
        assert member.device.ieee in member_ieee_addresses
        assert member.group == zha_group
        assert member.endpoint is not None

    entity_domains = GROUP_PROBE.determine_entity_domains(hass, zha_group)
    assert len(entity_domains) == 2

    assert Platform.LIGHT in entity_domains
    assert Platform.FAN in entity_domains

    entity_id = async_find_group_entity_id(hass, Platform.FAN, zha_group)
    assert hass.states.get(entity_id) is not None

    group_fan_cluster = zha_group.endpoint[hvac.Fan.cluster_id]

    await async_enable_traffic(hass, [device_fan_1, device_fan_2], enabled=False)
    await async_wait_for_updates(hass)
    # test that the fans were created and that they are unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [device_fan_1, device_fan_2])
    await async_wait_for_updates(hass)
    # test that the fan group entity was created and is off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    group_fan_cluster.write_attributes.reset_mock()

    with pytest.raises(HomeAssistantError):
        await async_turn_on(hass, entity_id)

    await hass.async_block_till_done()
    assert len(group_fan_cluster.write_attributes.mock_calls) == 1
    assert group_fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 2}


@pytest.mark.parametrize(
    ("plug_read", "expected_state", "expected_percentage"),
    [
        (None, STATE_OFF, None),
        ({"fan_mode": 0}, STATE_OFF, 0),
        ({"fan_mode": 1}, STATE_ON, 33),
        ({"fan_mode": 2}, STATE_ON, 66),
        ({"fan_mode": 3}, STATE_ON, 100),
    ],
)
async def test_fan_init(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device,
    plug_read,
    expected_state,
    expected_percentage,
) -> None:
    """Test ZHA fan platform."""

    cluster = zigpy_device.endpoints.get(1).fan
    cluster.PLUGGED_ATTR_READS = plug_read

    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == expected_state
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == expected_percentage
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is None


async def test_fan_update_entity(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device,
) -> None:
    """Test ZHA fan platform."""

    cluster = zigpy_device.endpoints.get(1).fan
    cluster.PLUGGED_ATTR_READS = {"fan_mode": 0}

    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_OFF
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 0
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is None
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE_STEP] == 100 / 3
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 2
    else:
        assert cluster.read_attributes.await_count == 4

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 3
    else:
        assert cluster.read_attributes.await_count == 5

    cluster.PLUGGED_ATTR_READS = {"fan_mode": 1}
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 33
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is None
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE_STEP] == 100 / 3
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 4
    else:
        assert cluster.read_attributes.await_count == 6


@pytest.fixture
def zigpy_device_ikea(zigpy_device_mock):
    """Ikea fan zigpy device."""
    endpoints = {
        1: {
            SIG_EP_INPUT: [
                general.Basic.cluster_id,
                general.Identify.cluster_id,
                general.Groups.cluster_id,
                general.Scenes.cluster_id,
                64637,
            ],
            SIG_EP_OUTPUT: [],
            SIG_EP_TYPE: zha.DeviceType.COMBINED_INTERFACE,
            SIG_EP_PROFILE: zha.PROFILE_ID,
        },
    }
    return zigpy_device_mock(
        endpoints,
        manufacturer="IKEA of Sweden",
        model="STARKVIND Air purifier",
        quirk=zhaquirks.ikea.starkvind.IkeaSTARKVIND,
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )


async def test_fan_ikea(
    hass: HomeAssistant,
    zha_device_joined_restored: ZHADevice,
    zigpy_device_ikea: Device,
) -> None:
    """Test ZHA fan Ikea platform."""
    zha_device = await zha_device_joined_restored(zigpy_device_ikea)
    cluster = zigpy_device_ikea.endpoints.get(1).ikea_airpurifier
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF
    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the fan was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at fan
    await send_attributes_report(hass, cluster, {6: 1})
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at fan
    await send_attributes_report(hass, cluster, {6: 0})
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    cluster.write_attributes.reset_mock()
    await async_turn_on(hass, entity_id)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 1}, manufacturer=None)
    ]

    # turn off from HA
    cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 0}, manufacturer=None)
    ]

    # change speed from HA
    cluster.write_attributes.reset_mock()
    await async_set_percentage(hass, entity_id, percentage=100)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 10}, manufacturer=None)
    ]

    # change preset_mode from HA
    cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_AUTO)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 1}, manufacturer=None)
    ]

    # set invalid preset_mode from HA
    cluster.write_attributes.reset_mock()
    with pytest.raises(NotValidPresetModeError) as exc:
        await async_set_preset_mode(
            hass, entity_id, preset_mode="invalid does not exist"
        )
    assert exc.value.translation_key == "not_valid_preset_mode"
    assert len(cluster.write_attributes.mock_calls) == 0

    # test adding new fan to the network and HA
    await async_test_rejoin(hass, zigpy_device_ikea, [cluster], (9,))


@pytest.mark.parametrize(
    (
        "ikea_plug_read",
        "ikea_expected_state",
        "ikea_expected_percentage",
        "ikea_preset_mode",
    ),
    [
        (None, STATE_OFF, None, None),
        ({"fan_mode": 0}, STATE_OFF, 0, None),
        ({"fan_mode": 1}, STATE_ON, 10, PRESET_MODE_AUTO),
        ({"fan_mode": 10}, STATE_ON, 20, "Speed 1"),
        ({"fan_mode": 15}, STATE_ON, 30, "Speed 1.5"),
        ({"fan_mode": 20}, STATE_ON, 40, "Speed 2"),
        ({"fan_mode": 25}, STATE_ON, 50, "Speed 2.5"),
        ({"fan_mode": 30}, STATE_ON, 60, "Speed 3"),
        ({"fan_mode": 35}, STATE_ON, 70, "Speed 3.5"),
        ({"fan_mode": 40}, STATE_ON, 80, "Speed 4"),
        ({"fan_mode": 45}, STATE_ON, 90, "Speed 4.5"),
        ({"fan_mode": 50}, STATE_ON, 100, "Speed 5"),
    ],
)
async def test_fan_ikea_init(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device_ikea,
    ikea_plug_read,
    ikea_expected_state,
    ikea_expected_percentage,
    ikea_preset_mode,
) -> None:
    """Test ZHA fan platform."""
    cluster = zigpy_device_ikea.endpoints.get(1).ikea_airpurifier
    cluster.PLUGGED_ATTR_READS = ikea_plug_read

    zha_device = await zha_device_joined_restored(zigpy_device_ikea)
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == ikea_expected_state
    assert (
        hass.states.get(entity_id).attributes[ATTR_PERCENTAGE]
        == ikea_expected_percentage
    )
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] == ikea_preset_mode


async def test_fan_ikea_update_entity(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device_ikea,
) -> None:
    """Test ZHA fan platform."""
    cluster = zigpy_device_ikea.endpoints.get(1).ikea_airpurifier
    cluster.PLUGGED_ATTR_READS = {"fan_mode": 0}

    zha_device = await zha_device_joined_restored(zigpy_device_ikea)
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_OFF
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 0
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is None
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE_STEP] == 100 / 10
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 3
    else:
        assert cluster.read_attributes.await_count == 6

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 4
    else:
        assert cluster.read_attributes.await_count == 7

    cluster.PLUGGED_ATTR_READS = {"fan_mode": 1}
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 10
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is PRESET_MODE_AUTO
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE_STEP] == 100 / 10
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 5
    else:
        assert cluster.read_attributes.await_count == 8


@pytest.fixture
def zigpy_device_kof(zigpy_device_mock):
    """Fan by King of Fans zigpy device."""
    endpoints = {
        1: {
            SIG_EP_INPUT: [
                general.Basic.cluster_id,
                general.Identify.cluster_id,
                general.Groups.cluster_id,
                general.Scenes.cluster_id,
                64637,
            ],
            SIG_EP_OUTPUT: [],
            SIG_EP_TYPE: zha.DeviceType.COMBINED_INTERFACE,
            SIG_EP_PROFILE: zha.PROFILE_ID,
        },
    }
    return zigpy_device_mock(
        endpoints,
        manufacturer="King Of Fans, Inc.",
        model="HBUniversalCFRemote",
        quirk=zhaquirks.kof.kof_mr101z.CeilingFan,
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )


async def test_fan_kof(
    hass: HomeAssistant,
    zha_device_joined_restored: ZHADevice,
    zigpy_device_kof: Device,
) -> None:
    """Test ZHA fan platform for King of Fans."""
    zha_device = await zha_device_joined_restored(zigpy_device_kof)
    cluster = zigpy_device_kof.endpoints.get(1).fan
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF
    await async_enable_traffic(hass, [zha_device], enabled=False)
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
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 2}, manufacturer=None)
    ]

    # turn off from HA
    cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 0}, manufacturer=None)
    ]

    # change speed from HA
    cluster.write_attributes.reset_mock()
    await async_set_percentage(hass, entity_id, percentage=100)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 4}, manufacturer=None)
    ]

    # change preset_mode from HA
    cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_SMART)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 6}, manufacturer=None)
    ]

    # set invalid preset_mode from HA
    cluster.write_attributes.reset_mock()
    with pytest.raises(NotValidPresetModeError) as exc:
        await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_AUTO)
    assert exc.value.translation_key == "not_valid_preset_mode"
    assert len(cluster.write_attributes.mock_calls) == 0

    # test adding new fan to the network and HA
    await async_test_rejoin(hass, zigpy_device_kof, [cluster], (1,))


@pytest.mark.parametrize(
    ("plug_read", "expected_state", "expected_percentage", "expected_preset"),
    [
        (None, STATE_OFF, None, None),
        ({"fan_mode": 0}, STATE_OFF, 0, None),
        ({"fan_mode": 1}, STATE_ON, 25, None),
        ({"fan_mode": 2}, STATE_ON, 50, None),
        ({"fan_mode": 3}, STATE_ON, 75, None),
        ({"fan_mode": 4}, STATE_ON, 100, None),
        ({"fan_mode": 6}, STATE_ON, None, PRESET_MODE_SMART),
    ],
)
async def test_fan_kof_init(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device_kof,
    plug_read,
    expected_state,
    expected_percentage,
    expected_preset,
) -> None:
    """Test ZHA fan platform for King of Fans."""

    cluster = zigpy_device_kof.endpoints.get(1).fan
    cluster.PLUGGED_ATTR_READS = plug_read

    zha_device = await zha_device_joined_restored(zigpy_device_kof)
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == expected_state
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == expected_percentage
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] == expected_preset


async def test_fan_kof_update_entity(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device_kof,
) -> None:
    """Test ZHA fan platform for King of Fans."""

    cluster = zigpy_device_kof.endpoints.get(1).fan
    cluster.PLUGGED_ATTR_READS = {"fan_mode": 0}

    zha_device = await zha_device_joined_restored(zigpy_device_kof)
    entity_id = find_entity_id(Platform.FAN, zha_device, hass)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_OFF
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 0
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is None
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE_STEP] == 100 / 4
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 2
    else:
        assert cluster.read_attributes.await_count == 4

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 3
    else:
        assert cluster.read_attributes.await_count == 5

    cluster.PLUGGED_ATTR_READS = {"fan_mode": 1}
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 25
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] is None
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE_STEP] == 100 / 4
    if zha_device_joined_restored.name == "zha_device_joined":
        assert cluster.read_attributes.await_count == 4
    else:
        assert cluster.read_attributes.await_count == 6
