"""Test ZHA switch."""
from unittest.mock import AsyncMock, call, patch

import pytest
from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zigpy.exceptions import ZigbeeException
import zigpy.profiles.zha as zha
from zigpy.quirks import CustomCluster, CustomDevice
import zigpy.types as t
import zigpy.zcl.clusters.closures as closures
import zigpy.zcl.clusters.general as general
from zigpy.zcl.clusters.manufacturer_specific import ManufacturerSpecificCluster
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zha.core.group import GroupMember
from homeassistant.components.zha.core.helpers import get_zha_gateway
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from .common import (
    async_enable_traffic,
    async_find_group_entity_id,
    async_test_rejoin,
    async_wait_for_updates,
    find_entity_id,
    send_attributes_report,
    update_attribute_cache,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ON = 1
OFF = 0
IEEE_GROUPABLE_DEVICE = "01:2d:6f:00:0a:90:69:e8"
IEEE_GROUPABLE_DEVICE2 = "02:2d:6f:00:0a:90:69:e8"


@pytest.fixture(autouse=True)
def switch_platform_only():
    """Only set up the switch and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
        ),
    ):
        yield


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""
    endpoints = {
        1: {
            SIG_EP_INPUT: [general.Basic.cluster_id, general.OnOff.cluster_id],
            SIG_EP_OUTPUT: [],
            SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
        }
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
def zigpy_cover_device(zigpy_device_mock):
    """Zigpy cover device."""

    endpoints = {
        1: {
            SIG_EP_PROFILE: zha.PROFILE_ID,
            SIG_EP_TYPE: zha.DeviceType.WINDOW_COVERING_DEVICE,
            SIG_EP_INPUT: [
                general.Basic.cluster_id,
                closures.WindowCovering.cluster_id,
            ],
            SIG_EP_OUTPUT: [],
        }
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
async def coordinator(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA light platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
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
async def device_switch_1(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA switch platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.OnOff.cluster_id, general.Groups.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    await hass.async_block_till_done()
    return zha_device


@pytest.fixture
async def device_switch_2(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA switch platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.OnOff.cluster_id, general.Groups.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE2,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    await hass.async_block_till_done()
    return zha_device


async def test_switch(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device
) -> None:
    """Test ZHA switch platform."""

    zha_device = await zha_device_joined_restored(zigpy_device)
    cluster = zigpy_device.endpoints[1].on_off
    entity_id = find_entity_id(Platform.SWITCH, zha_device, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF
    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the switch was created and that its state is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    await send_attributes_report(hass, cluster, {1: 0, 0: 1, 2: 2})
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    await send_attributes_report(hass, cluster, {1: 1, 0: 0, 2: 2})
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        # turn on via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False,
            ON,
            cluster.commands_by_name["on"].schema,
            expect_reply=True,
            manufacturer=None,
            tsn=None,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_ON

    # turn off from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x01, zcl_f.Status.SUCCESS],
    ):
        # turn off via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False,
            OFF,
            cluster.commands_by_name["off"].schema,
            expect_reply=True,
            manufacturer=None,
            tsn=None,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF

    await async_setup_component(hass, "homeassistant", {})

    cluster.read_attributes.reset_mock()
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert len(cluster.read_attributes.mock_calls) == 1
    assert cluster.read_attributes.call_args == call(
        ["on_off"], allow_cache=False, only_cache=False, manufacturer=None
    )

    # test joining a new switch to the network and HA
    await async_test_rejoin(hass, zigpy_device, [cluster], (1,))


class WindowDetectionFunctionQuirk(CustomDevice):
    """Quirk with window detection function attribute."""

    class TuyaManufCluster(CustomCluster, ManufacturerSpecificCluster):
        """Tuya manufacturer specific cluster."""

        cluster_id = 0xEF00
        ep_attribute = "tuya_manufacturer"

        attributes = {
            0xEF01: ("window_detection_function", t.Bool),
            0xEF02: ("window_detection_function_inverter", t.Bool),
        }

        def __init__(self, *args, **kwargs):
            """Initialize with task."""
            super().__init__(*args, **kwargs)
            self._attr_cache.update(
                {0xEF01: False}
            )  # entity won't be created without this

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                INPUT_CLUSTERS: [general.Basic.cluster_id, TuyaManufCluster],
                OUTPUT_CLUSTERS: [],
            },
        }
    }


@pytest.fixture
async def zigpy_device_tuya(hass, zigpy_device_mock, zha_device_joined):
    """Device tracker zigpy tuya device."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
            }
        },
        manufacturer="_TZE200_b6wax7g0",
        quirk=WindowDetectionFunctionQuirk,
    )

    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    await hass.async_block_till_done()
    return zigpy_device


@patch(
    "homeassistant.components.zha.entity.DEFAULT_UPDATE_GROUP_FROM_CHILD_DELAY",
    new=0,
)
async def test_zha_group_switch_entity(
    hass: HomeAssistant, device_switch_1, device_switch_2, coordinator
) -> None:
    """Test the switch entity for a ZHA group."""
    zha_gateway = get_zha_gateway(hass)
    assert zha_gateway is not None
    zha_gateway.coordinator_zha_device = coordinator
    coordinator._zha_gateway = zha_gateway
    device_switch_1._zha_gateway = zha_gateway
    device_switch_2._zha_gateway = zha_gateway
    member_ieee_addresses = [device_switch_1.ieee, device_switch_2.ieee]
    members = [
        GroupMember(device_switch_1.ieee, 1),
        GroupMember(device_switch_2.ieee, 1),
    ]

    # test creating a group with 2 members
    zha_group = await zha_gateway.async_create_zigpy_group("Test Group", members)
    await hass.async_block_till_done()

    assert zha_group is not None
    assert len(zha_group.members) == 2
    for member in zha_group.members:
        assert member.device.ieee in member_ieee_addresses
        assert member.group == zha_group
        assert member.endpoint is not None

    entity_id = async_find_group_entity_id(hass, Platform.SWITCH, zha_group)
    assert hass.states.get(entity_id) is not None

    group_cluster_on_off = zha_group.endpoint[general.OnOff.cluster_id]
    dev1_cluster_on_off = device_switch_1.device.endpoints[1].on_off
    dev2_cluster_on_off = device_switch_2.device.endpoints[1].on_off

    await async_enable_traffic(hass, [device_switch_1, device_switch_2], enabled=False)
    await async_wait_for_updates(hass)

    # test that the switches were created and that they are off
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [device_switch_1, device_switch_2])
    await async_wait_for_updates(hass)

    # test that the switches were created and are off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        # turn on via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert len(group_cluster_on_off.request.mock_calls) == 1
        assert group_cluster_on_off.request.call_args == call(
            False,
            ON,
            group_cluster_on_off.commands_by_name["on"].schema,
            expect_reply=True,
            manufacturer=None,
            tsn=None,
        )
    assert hass.states.get(entity_id).state == STATE_ON

    # test turn off failure case
    hold_off = group_cluster_on_off.off
    group_cluster_on_off.off = AsyncMock(return_value=[0x01, zcl_f.Status.FAILURE])
    # turn off via UI
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(group_cluster_on_off.off.mock_calls) == 1

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    group_cluster_on_off.off = hold_off

    # turn off from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x01, zcl_f.Status.SUCCESS],
    ):
        # turn off via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert len(group_cluster_on_off.request.mock_calls) == 1
        assert group_cluster_on_off.request.call_args == call(
            False,
            OFF,
            group_cluster_on_off.commands_by_name["off"].schema,
            expect_reply=True,
            manufacturer=None,
            tsn=None,
        )
    assert hass.states.get(entity_id).state == STATE_OFF

    # test turn on failure case
    hold_on = group_cluster_on_off.on
    group_cluster_on_off.on = AsyncMock(return_value=[0x01, zcl_f.Status.FAILURE])
    # turn on via UI
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert len(group_cluster_on_off.on.mock_calls) == 1

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    group_cluster_on_off.on = hold_on

    # test some of the group logic to make sure we key off states correctly
    await send_attributes_report(hass, dev1_cluster_on_off, {0: 1})
    await send_attributes_report(hass, dev2_cluster_on_off, {0: 1})
    await async_wait_for_updates(hass)

    # test that group switch is on
    assert hass.states.get(entity_id).state == STATE_ON

    await send_attributes_report(hass, dev1_cluster_on_off, {0: 0})
    await async_wait_for_updates(hass)

    # test that group switch is still on
    assert hass.states.get(entity_id).state == STATE_ON

    await send_attributes_report(hass, dev2_cluster_on_off, {0: 0})
    await async_wait_for_updates(hass)

    # test that group switch is now off
    assert hass.states.get(entity_id).state == STATE_OFF

    await send_attributes_report(hass, dev1_cluster_on_off, {0: 1})
    await async_wait_for_updates(hass)

    # test that group switch is now back on
    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_configurable(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device_tuya
) -> None:
    """Test ZHA configurable switch platform."""

    zha_device = await zha_device_joined_restored(zigpy_device_tuya)
    cluster = zigpy_device_tuya.endpoints[1].tuya_manufacturer
    entity_id = find_entity_id(Platform.SWITCH, zha_device, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF
    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the switch was created and that its state is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    await send_attributes_report(hass, cluster, {"window_detection_function": True})
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    await send_attributes_report(hass, cluster, {"window_detection_function": False})
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    with patch(
        "zigpy.zcl.Cluster.write_attributes",
        return_value=[zcl_f.Status.SUCCESS, zcl_f.Status.SUCCESS],
    ):
        # turn on via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.write_attributes.mock_calls == [
            call({"window_detection_function": True}, manufacturer=None)
        ]

    cluster.write_attributes.reset_mock()

    # turn off from HA
    with patch(
        "zigpy.zcl.Cluster.write_attributes",
        return_value=[zcl_f.Status.SUCCESS, zcl_f.Status.SUCCESS],
    ):
        # turn off via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.write_attributes.mock_calls == [
            call({"window_detection_function": False}, manufacturer=None)
        ]

    cluster.read_attributes.reset_mock()
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    # the mocking doesn't update the attr cache so this flips back to initial value
    assert cluster.read_attributes.call_count == 2
    assert [
        call(
            [
                "window_detection_function",
            ],
            allow_cache=False,
            only_cache=False,
            manufacturer=None,
        ),
        call(
            [
                "window_detection_function_inverter",
            ],
            allow_cache=False,
            only_cache=False,
            manufacturer=None,
        ),
    ] == cluster.read_attributes.call_args_list

    cluster.write_attributes.reset_mock()
    cluster.write_attributes.side_effect = ZigbeeException

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )

    assert cluster.write_attributes.mock_calls == [
        call({"window_detection_function": False}, manufacturer=None),
        call({"window_detection_function": False}, manufacturer=None),
        call({"window_detection_function": False}, manufacturer=None),
    ]

    cluster.write_attributes.side_effect = None

    # test inverter
    cluster.write_attributes.reset_mock()
    cluster._attr_cache.update({0xEF02: True})

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert cluster.write_attributes.mock_calls == [
        call({"window_detection_function": True}, manufacturer=None)
    ]

    cluster.write_attributes.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert cluster.write_attributes.mock_calls == [
        call({"window_detection_function": False}, manufacturer=None)
    ]

    # test joining a new switch to the network and HA
    await async_test_rejoin(hass, zigpy_device_tuya, [cluster], (0,))


WCAttrs = closures.WindowCovering.AttributeDefs
WCT = closures.WindowCovering.WindowCoveringType
WCCS = closures.WindowCovering.ConfigStatus
WCM = closures.WindowCovering.WindowCoveringMode


async def test_cover_inversion_switch(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_cover_device
) -> None:
    """Test ZHA cover platform."""

    # load up cover domain
    cluster = zigpy_cover_device.endpoints[1].window_covering
    cluster.PLUGGED_ATTR_READS = {
        WCAttrs.current_position_lift_percentage.name: 65,
        WCAttrs.current_position_tilt_percentage.name: 42,
        WCAttrs.window_covering_type.name: WCT.Tilt_blind_tilt_and_lift,
        WCAttrs.config_status.name: WCCS(~WCCS.Open_up_commands_reversed),
        WCAttrs.window_covering_mode.name: WCM(WCM.LEDs_display_feedback),
    }
    update_attribute_cache(cluster)
    zha_device = await zha_device_joined_restored(zigpy_cover_device)
    assert (
        not zha_device.endpoints[1]
        .all_cluster_handlers[f"1:0x{cluster.cluster_id:04x}"]
        .inverted
    )
    assert cluster.read_attributes.call_count == 3
    assert (
        WCAttrs.current_position_lift_percentage.name
        in cluster.read_attributes.call_args[0][0]
    )
    assert (
        WCAttrs.current_position_tilt_percentage.name
        in cluster.read_attributes.call_args[0][0]
    )

    entity_id = find_entity_id(Platform.SWITCH, zha_device, hass)
    assert entity_id is not None

    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the cover was created and that it is unavailable
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()

    # test update
    prev_call_count = cluster.read_attributes.call_count
    await async_update_entity(hass, entity_id)
    assert cluster.read_attributes.call_count == prev_call_count + 1
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    # test to see the state remains after tilting to 0%
    await send_attributes_report(
        hass, cluster, {WCAttrs.current_position_tilt_percentage.id: 0}
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    with patch(
        "zigpy.zcl.Cluster.write_attributes", return_value=[0x1, zcl_f.Status.SUCCESS]
    ):
        cluster.PLUGGED_ATTR_READS = {
            WCAttrs.config_status.name: WCCS.Operational
            | WCCS.Open_up_commands_reversed,
        }
        # turn on from UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.write_attributes.call_count == 1
        assert cluster.write_attributes.call_args_list[0] == call(
            {
                WCAttrs.window_covering_mode.name: WCM.Motor_direction_reversed
                | WCM.LEDs_display_feedback
            },
            manufacturer=None,
        )

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_ON

        cluster.write_attributes.reset_mock()

        # turn off from UI
        cluster.PLUGGED_ATTR_READS = {
            WCAttrs.config_status.name: WCCS.Operational,
        }
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.write_attributes.call_count == 1
        assert cluster.write_attributes.call_args_list[0] == call(
            {WCAttrs.window_covering_mode.name: WCM.LEDs_display_feedback},
            manufacturer=None,
        )

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF

        cluster.write_attributes.reset_mock()

        # test that sending the command again does not result in a write
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.write_attributes.call_count == 0

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF


async def test_cover_inversion_switch_not_created(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_cover_device
) -> None:
    """Test ZHA cover platform."""

    # load up cover domain
    cluster = zigpy_cover_device.endpoints[1].window_covering
    cluster.PLUGGED_ATTR_READS = {
        WCAttrs.current_position_lift_percentage.name: 65,
        WCAttrs.current_position_tilt_percentage.name: 42,
        WCAttrs.config_status.name: WCCS(~WCCS.Open_up_commands_reversed),
    }
    update_attribute_cache(cluster)
    zha_device = await zha_device_joined_restored(zigpy_cover_device)

    assert cluster.read_attributes.call_count == 3
    assert (
        WCAttrs.current_position_lift_percentage.name
        in cluster.read_attributes.call_args[0][0]
    )
    assert (
        WCAttrs.current_position_tilt_percentage.name
        in cluster.read_attributes.call_args[0][0]
    )

    # entity should not be created when mode or config status aren't present
    entity_id = find_entity_id(Platform.SWITCH, zha_device, hass)
    assert entity_id is None
