"""Test ZHA entities."""

import asyncio
from collections.abc import Callable, Coroutine
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from zigpy.application import ControllerApplication
from zigpy.device import ZigbeeDevice
from zigpy.profiles import zha
from zigpy.types import EUI64
from zigpy.zcl.clusters import general, hvac
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zha import const as zha_const
from homeassistant.components.zha.const import DOMAIN
from homeassistant.components.zha.helpers import get_zha_gateway, get_zha_gateway_proxy
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import find_entity_id, send_attributes_report
from .conftest import (
    FIXTURE_GRP_WITH_ENTITIES_ID,
    FIXTURE_GRP_WITH_ENTITIES_NAME,
    SIG_EP_INPUT,
    SIG_EP_OUTPUT,
    SIG_EP_PROFILE,
    SIG_EP_TYPE,
)


async def test_device_registry_via_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a ZHA device links to the coordinator device via via_device_id."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
    )

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    coordinator_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(gateway.state.node_info.ieee)), config_entry.entry_id
    )
    assert coordinator_device is not None
    # The coordinator itself is not linked to a via device
    assert coordinator_device.via_device_id is None

    reg_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(zha_device.ieee)), config_entry.entry_id
    )
    assert reg_device is not None
    assert reg_device.via_device_id == coordinator_device.id


async def test_device_registry_via_device_without_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a ZHA device without entities links to the coordinator device."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="11:22:33:44:55:66:77:88",
    )

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not zha_device.platform_entities

    coordinator_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(gateway.state.node_info.ieee)), config_entry.entry_id
    )
    assert coordinator_device is not None

    reg_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(zha_device.ieee)), config_entry.entry_id
    )
    assert reg_device is not None
    assert reg_device.via_device_id == coordinator_device.id


async def test_group_entity_name_and_device_info(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that group entities use group device info and return None for name."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    # Find the group entity
    entity_entries = er.async_entries_for_device(
        entity_registry, group_proxy.device_id, include_disabled_entities=True
    )
    assert len(entity_entries) > 0

    # The entity should use the group device name (friendly name = group name)
    entity = hass.states.get(entity_entries[0].entity_id)
    assert entity is not None
    assert entity.name == FIXTURE_GRP_WITH_ENTITIES_NAME

    # Verify device info points to the group device
    device = device_registry.async_get(group_proxy.device_id)
    assert device is not None
    config_entry_id = gateway_proxy.config_entry.entry_id
    expected_identifier = (
        f"{config_entry_id}_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}"
    )
    assert group_proxy.device_identifier == expected_identifier
    assert ("zha", expected_identifier) in device.identifiers
    assert device.manufacturer == "Zigbee"
    assert device.model == "Group"
    assert device.entry_type == dr.DeviceEntryType.SERVICE


async def test_group_entity_context_propagation(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test propagating service call context from a ZHA group entity to members."""
    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    ieee_2 = EUI64.convert("01:2d:6f:00:0a:90:69:e2")

    # Add a second switch endpoint on device 1 that is NOT a member of the group
    device_1 = zigpy_app_controller_with_group.devices[ieee_1]
    ep_2 = device_1.add_endpoint(2)
    ep_2.profile_id = zha.PROFILE_ID
    ep_2.device_type = zha.DeviceType.ON_OFF_SWITCH
    ep_2.add_input_cluster(general.Basic.cluster_id)
    ep_2.add_input_cluster(general.OnOff.cluster_id)

    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    dev_proxy_2 = gateway_proxy.device_proxies[ieee_2]

    member_1_entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{ieee_1}-1-{general.OnOff.cluster_id}"
    )
    non_member_switch_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{ieee_1}-2-{general.OnOff.cluster_id}"
    )
    member_2_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_2, hass)
    assert member_1_entity_id is not None
    assert non_member_switch_id is not None
    assert member_2_entity_id is not None

    cluster_1 = device_1.endpoints[1].on_off
    cluster_1_ep2 = device_1.endpoints[2].on_off
    cluster_2 = zigpy_app_controller_with_group.devices[ieee_2].endpoints[1].on_off

    turn_on_context = Context(user_id=hass_admin_user.id, id="turn_on_ctx")
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_on_context,
    )

    group_state = hass.states.get(group_entity_id)
    assert group_state is not None
    assert group_state.state == STATE_ON
    assert group_state.context == turn_on_context

    # Attribute reports arriving for the group members inherit the group context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    await send_attributes_report(
        hass, cluster_1_ep2, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    await send_attributes_report(
        hass, cluster_2, {general.OnOff.AttributeDefs.on_off.id: 1}
    )

    member_1_state = hass.states.get(member_1_entity_id)
    member_2_state = hass.states.get(member_2_entity_id)
    non_member_state = hass.states.get(non_member_switch_id)
    assert member_1_state is not None
    assert member_1_state.state == STATE_ON
    assert member_1_state.context == turn_on_context
    assert member_2_state is not None
    assert member_2_state.state == STATE_ON
    assert member_2_state.context == turn_on_context

    # Non-group entities on the same device must not inherit the group context
    assert non_member_state is not None
    assert non_member_state.state == STATE_ON
    assert non_member_state.context != turn_on_context

    # An opposing state change (turning off) within the 5-second window must not
    # inherit the turn_on context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    member_1_off_state = hass.states.get(member_1_entity_id)
    assert member_1_off_state is not None
    assert member_1_off_state.state == STATE_OFF
    assert member_1_off_state.context != turn_on_context

    # After the context window expires, even a matching state change gets a fresh context
    turn_off_context = Context(user_id=hass_admin_user.id, id="turn_off_ctx")
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_off_context,
    )
    with (
        patch("homeassistant.helpers.entity.CONTEXT_RECENT_TIME_SECONDS", 1),
        patch("homeassistant.helpers.entity.timer", return_value=time.time() + 2),
    ):
        await send_attributes_report(
            hass, cluster_2, {general.OnOff.AttributeDefs.on_off.id: 0}
        )

    member_2_off_state = hass.states.get(member_2_entity_id)
    assert member_2_off_state is not None
    assert member_2_off_state.state == STATE_OFF
    assert member_2_off_state.context != turn_off_context


@pytest.mark.usefixtures("zigpy_app_controller_with_group")
async def test_group_entity_context_propagation_mixed_platforms(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller: ControllerApplication,
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test context propagation across platforms in a mixed light and switch group."""
    group = zigpy_app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    for ieee in ("01:2d:6f:00:0a:90:69:f1", "01:2d:6f:00:0a:90:69:f2"):
        light = zigpy_device_mock(
            {
                1: {
                    SIG_EP_INPUT: [
                        general.OnOff.cluster_id,
                        general.LevelControl.cluster_id,
                        general.Basic.cluster_id,
                        general.Groups.cluster_id,
                    ],
                    SIG_EP_OUTPUT: [],
                    SIG_EP_TYPE: zha.DeviceType.DIMMABLE_LIGHT,
                    SIG_EP_PROFILE: zha.PROFILE_ID,
                }
            },
            ieee=ieee,
        )
        zigpy_app_controller.devices[light.ieee] = light
        group.add_member(light.endpoints[1], suppress_event=True)

    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            zha_const.CUSTOM_CONFIGURATION: {
                zha_const.ZHA_OPTIONS: {
                    zha_const.CONF_ENABLE_LIGHT_TRANSITIONING_FLAG: False,
                    zha_const.CONF_GROUP_MEMBERS_ASSUME_STATE: True,
                },
            }
        },
    )
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    light_group_entity_id = entity_registry.async_get_entity_id(
        Platform.LIGHT,
        DOMAIN,
        f"light_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
    )
    assert light_group_entity_id is not None

    light_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:f1")
    light_2_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:f2")
    switch_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:e1")

    light_1_id = find_entity_id(
        Platform.LIGHT, gateway_proxy.device_proxies[light_1_ieee], hass
    )
    light_2_id = find_entity_id(
        Platform.LIGHT, gateway_proxy.device_proxies[light_2_ieee], hass
    )
    switch_1_id = find_entity_id(
        Platform.SWITCH, gateway_proxy.device_proxies[switch_1_ieee], hass
    )
    assert light_1_id is not None
    assert light_2_id is not None
    assert switch_1_id is not None

    group_context = Context(user_id=hass_admin_user.id, id="mixed_group_ctx")
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_group_entity_id},
        blocking=True,
        context=group_context,
    )

    # Light members optimistically assume the group state with the propagated context
    light_1_state = hass.states.get(light_1_id)
    light_2_state = hass.states.get(light_2_id)
    assert light_1_state is not None
    assert light_1_state.state == STATE_ON
    assert light_1_state.context == group_context
    assert light_2_state is not None
    assert light_2_state.state == STATE_ON
    assert light_2_state.context == group_context

    # Switch member in the same Zigbee group also receives the propagated context
    switch_1_cluster = zigpy_app_controller.devices[switch_1_ieee].endpoints[1].on_off
    await send_attributes_report(
        hass, switch_1_cluster, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    switch_1_state = hass.states.get(switch_1_id)
    assert switch_1_state is not None
    assert switch_1_state.state == STATE_ON
    assert switch_1_state.context == group_context

    # Turning a member light off within the 5-second window does not reuse group_context
    light_1_cluster = zigpy_app_controller.devices[light_1_ieee].endpoints[1].on_off
    await send_attributes_report(
        hass, light_1_cluster, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    light_1_off_state = hass.states.get(light_1_id)
    assert light_1_off_state is not None
    assert light_1_off_state.state == STATE_OFF
    assert light_1_off_state.context != group_context


@pytest.mark.usefixtures("zigpy_app_controller_with_group")
async def test_group_entity_context_brightness_report_before_on(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller: ControllerApplication,
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a brightness report arriving before OnOff does not clear group context."""
    group = zigpy_app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    for ieee in ("01:2d:6f:00:0a:90:69:f1", "01:2d:6f:00:0a:90:69:f2"):
        light = zigpy_device_mock(
            {
                1: {
                    SIG_EP_INPUT: [
                        general.OnOff.cluster_id,
                        general.LevelControl.cluster_id,
                        general.Basic.cluster_id,
                        general.Groups.cluster_id,
                    ],
                    SIG_EP_OUTPUT: [],
                    SIG_EP_TYPE: zha.DeviceType.DIMMABLE_LIGHT,
                    SIG_EP_PROFILE: zha.PROFILE_ID,
                }
            },
            ieee=ieee,
        )
        zigpy_app_controller.devices[light.ieee] = light
        group.add_member(light.endpoints[1], suppress_event=True)

    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            zha_const.CUSTOM_CONFIGURATION: {
                zha_const.ZHA_OPTIONS: {
                    zha_const.CONF_ENABLE_LIGHT_TRANSITIONING_FLAG: False,
                    zha_const.CONF_GROUP_MEMBERS_ASSUME_STATE: False,
                },
            }
        },
    )
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    light_group_entity_id = entity_registry.async_get_entity_id(
        Platform.LIGHT,
        DOMAIN,
        f"light_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
    )
    assert light_group_entity_id is not None

    light_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:f1")
    light_1_id = find_entity_id(
        Platform.LIGHT, gateway_proxy.device_proxies[light_1_ieee], hass
    )
    assert light_1_id is not None

    group_context = Context(user_id=hass_admin_user.id, id="brightness_first_ctx")
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_group_entity_id, ATTR_BRIGHTNESS: 200},
        blocking=True,
        context=group_context,
    )

    light_1_ep = zigpy_app_controller.devices[light_1_ieee].endpoints[1]

    # Brightness report arrives while the member light is still off
    await send_attributes_report(
        hass,
        light_1_ep.level,
        {general.LevelControl.AttributeDefs.current_level.id: 200},
    )
    # Followed by the OnOff report turning the light on
    await send_attributes_report(
        hass,
        light_1_ep.on_off,
        {general.OnOff.AttributeDefs.on_off.id: 1},
    )

    light_1_state = hass.states.get(light_1_id)
    assert light_1_state is not None
    assert light_1_state.state == STATE_ON
    assert light_1_state.attributes[ATTR_BRIGHTNESS] == 200
    assert light_1_state.context == group_context


async def test_group_entity_context_in_flight_member_report(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a member report arriving while the multicast command is still in flight."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    ieee_2 = EUI64.convert("01:2d:6f:00:0a:90:69:e2")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    dev_proxy_2 = gateway_proxy.device_proxies[ieee_2]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    member_2_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_2, hass)
    assert member_1_entity_id is not None
    assert member_2_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off
    cluster_2 = zigpy_app_controller_with_group.devices[ieee_2].endpoints[1].on_off
    # Member 2 starts on so it can report an opposing off transition while turn_on is in flight
    await send_attributes_report(
        hass, cluster_2, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    assert hass.states.get(member_2_entity_id).state == STATE_ON

    group_on_off_cluster = group_proxy.group.zigpy_group.endpoint[
        general.OnOff.cluster_id
    ]
    orig_on = group_on_off_cluster.on

    async def _on_with_early_member_report(*args: Any, **kwargs: Any) -> Any:
        result = await orig_on(*args, **kwargs)
        await send_attributes_report(
            hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
        )
        await send_attributes_report(
            hass, cluster_2, {general.OnOff.AttributeDefs.on_off.id: 0}
        )
        return result

    with patch.object(
        group_on_off_cluster, "on", side_effect=_on_with_early_member_report
    ):
        turn_on_context = Context(user_id=hass_admin_user.id, id="in_flight_ctx")
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: group_entity_id},
            blocking=True,
            context=turn_on_context,
        )

    member_1_state = hass.states.get(member_1_entity_id)
    assert member_1_state is not None
    assert member_1_state.state == STATE_ON
    assert member_1_state.context == turn_on_context

    member_2_state = hass.states.get(member_2_entity_id)
    assert member_2_state is not None
    assert member_2_state.state == STATE_OFF
    assert member_2_state.context != turn_on_context


async def test_group_entity_context_no_diff_and_delayed_group_event(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test group context when a command emits no diff and a group event fires later."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id
    zha_group_entity = group_proxy.group.group_entities[group_entry.unique_id]

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    ieee_2 = EUI64.convert("01:2d:6f:00:0a:90:69:e2")
    member_1_entity_id = find_entity_id(
        Platform.SWITCH, gateway_proxy.device_proxies[ieee_1], hass
    )
    member_2_entity_id = find_entity_id(
        Platform.SWITCH, gateway_proxy.device_proxies[ieee_2], hass
    )
    assert member_1_entity_id is not None
    assert member_2_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off
    cluster_2 = zigpy_app_controller_with_group.devices[ieee_2].endpoints[1].on_off

    # Member 1 is already on, making the group entity already on (while member 2 is off)
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    zha_group_entity.update()
    await hass.async_block_till_done()
    assert hass.states.get(group_entity_id).state == STATE_ON

    # Calling turn_on when the group is already on emits no state diff on SwitchGroup
    turn_on_context = Context(user_id=hass_admin_user.id, id="no_diff_turn_on_ctx")
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_on_context,
    )

    # Opposing state change (turning off) on member 1 must still be rejected
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    member_1_off_state = hass.states.get(member_1_entity_id)
    assert member_1_off_state is not None
    assert member_1_off_state.state == STATE_OFF
    assert member_1_off_state.context != turn_on_context

    # After the context window expires, a delayed group state event must not revive
    # the expired context with a fresh timestamp on member 2
    later = time.time() + 10
    with (
        patch("homeassistant.helpers.entity.timer", return_value=later),
        patch("time.time", return_value=later),
    ):
        zha_group_entity.update()
        await hass.async_block_till_done()
        await send_attributes_report(
            hass, cluster_2, {general.OnOff.AttributeDefs.on_off.id: 1}
        )

    member_2_state = hass.states.get(member_2_entity_id)
    assert member_2_state is not None
    assert member_2_state.state == STATE_ON
    assert member_2_state.context != turn_on_context


@pytest.mark.usefixtures("zigpy_app_controller_with_group")
async def test_fan_group_entity_context_propagation(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller: ControllerApplication,
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test context propagation for a ZHA fan group where group state lags members."""
    group = zigpy_app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    for ieee in ("01:2d:6f:00:0a:90:69:d1", "01:2d:6f:00:0a:90:69:d2"):
        fan_dev = zigpy_device_mock(
            {
                1: {
                    SIG_EP_INPUT: [
                        general.Basic.cluster_id,
                        general.Groups.cluster_id,
                        hvac.Fan.cluster_id,
                    ],
                    SIG_EP_OUTPUT: [],
                    SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                    SIG_EP_PROFILE: zha.PROFILE_ID,
                }
            },
            ieee=ieee,
        )
        zigpy_app_controller.devices[fan_dev.ieee] = fan_dev
        group.add_member(fan_dev.endpoints[1], suppress_event=True)

    await setup_zha()
    group.endpoint[hvac.Fan.cluster_id].write_attributes = AsyncMock(
        return_value=[[zcl_f.WriteAttributesStatusRecord(zcl_f.Status.SUCCESS)]]
    )

    gateway_proxy = get_zha_gateway_proxy(hass)
    fan_group_entity_id = entity_registry.async_get_entity_id(
        Platform.FAN,
        DOMAIN,
        f"fan_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
    )
    assert fan_group_entity_id is not None

    fan_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:d1")
    fan_1_id = find_entity_id(
        Platform.FAN, gateway_proxy.device_proxies[fan_1_ieee], hass
    )
    assert fan_1_id is not None
    fan_1_cluster = zigpy_app_controller.devices[fan_1_ieee].endpoints[1].fan

    switch_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    switch_1_id = find_entity_id(
        Platform.SWITCH, gateway_proxy.device_proxies[switch_1_ieee], hass
    )
    assert switch_1_id is not None
    switch_1_cluster = zigpy_app_controller.devices[switch_1_ieee].endpoints[1].on_off

    turn_on_context = Context(user_id=hass_admin_user.id, id="fan_turn_on_ctx")
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_group_entity_id},
        blocking=True,
        context=turn_on_context,
    )

    await send_attributes_report(
        hass,
        fan_1_cluster,
        {hvac.Fan.AttributeDefs.fan_mode.id: hvac.FanMode.Medium},
    )
    fan_1_state = hass.states.get(fan_1_id)
    assert fan_1_state is not None
    assert fan_1_state.state == STATE_ON
    assert fan_1_state.context == turn_on_context

    # An OnOff switch in the same Zigbee group is not controlled by FanGroup commands
    await send_attributes_report(
        hass,
        switch_1_cluster,
        {general.OnOff.AttributeDefs.on_off.id: 1},
    )
    switch_1_state = hass.states.get(switch_1_id)
    assert switch_1_state is not None
    assert switch_1_state.state == STATE_ON
    assert switch_1_state.context != turn_on_context

    # Opposing off report within the 5-second window must not inherit turn_on_context
    await send_attributes_report(
        hass,
        fan_1_cluster,
        {hvac.Fan.AttributeDefs.fan_mode.id: hvac.FanMode.Off},
    )
    fan_1_off_state = hass.states.get(fan_1_id)
    assert fan_1_off_state is not None
    assert fan_1_off_state.state == STATE_OFF
    assert fan_1_off_state.context != turn_on_context

    # After fan group turn_off, a physical Medium/on then High/on must not inherit turn_off_context
    turn_off_context = Context(user_id=hass_admin_user.id, id="fan_turn_off_ctx")
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: fan_group_entity_id},
        blocking=True,
        context=turn_off_context,
    )
    await send_attributes_report(
        hass,
        fan_1_cluster,
        {hvac.Fan.AttributeDefs.fan_mode.id: hvac.FanMode.Medium},
    )
    fan_1_medium_state = hass.states.get(fan_1_id)
    assert fan_1_medium_state is not None
    assert fan_1_medium_state.state == STATE_ON
    assert fan_1_medium_state.context != turn_off_context

    await send_attributes_report(
        hass,
        fan_1_cluster,
        {hvac.Fan.AttributeDefs.fan_mode.id: hvac.FanMode.High},
    )
    fan_1_high_state = hass.states.get(fan_1_id)
    assert fan_1_high_state is not None
    assert fan_1_high_state.state == STATE_ON
    assert fan_1_high_state.context != turn_off_context


async def test_group_entity_context_not_used_for_unavailable_transition(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a member becoming unavailable within 5s does not inherit group context."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    assert member_1_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off

    turn_on_context = Context(user_id=hass_admin_user.id, id="unavail_turn_on_ctx")
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_on_context,
    )

    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    member_1_state = hass.states.get(member_1_entity_id)
    assert member_1_state is not None
    assert member_1_state.state == STATE_ON
    assert member_1_state.context == turn_on_context

    # Device drops offline within the 5-second window
    dev_proxy_1.device.on_network = False
    await hass.async_block_till_done()

    member_1_unavail_state = hass.states.get(member_1_entity_id)
    assert member_1_unavail_state is not None
    assert member_1_unavail_state.state == STATE_UNAVAILABLE
    assert member_1_unavail_state.context != turn_on_context


async def test_group_entity_context_when_group_command_returns_non_success(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test group context expected state follows command intent even if group state stays off."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    assert member_1_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off
    group_on_off_cluster = group_proxy.group.zigpy_group.endpoint[
        general.OnOff.cluster_id
    ]

    with patch.object(
        group_on_off_cluster,
        "on",
        AsyncMock(return_value=[0x01, zcl_f.Status.FAILURE]),
    ):
        turn_on_context = Context(
            user_id=hass_admin_user.id, id="failed_group_turn_on_ctx"
        )
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: group_entity_id},
            blocking=True,
            context=turn_on_context,
        )

    # Even though SwitchGroup remained off because the group command returned FAILURE,
    # a member that received the multicast and turns on should inherit the context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    member_1_state = hass.states.get(member_1_entity_id)
    assert member_1_state is not None
    assert member_1_state.state == STATE_ON
    assert member_1_state.context == turn_on_context


async def test_group_entity_context_overlapping_commands(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an overlapping group command is not overwritten when an earlier call finishes."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    assert member_1_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    assert hass.states.get(member_1_entity_id).state == STATE_ON

    group_on_off_cluster = group_proxy.group.zigpy_group.endpoint[
        general.OnOff.cluster_id
    ]
    orig_on = group_on_off_cluster.on
    orig_off = group_on_off_cluster.off

    on_entered = asyncio.Event()
    release_on = asyncio.Event()
    off_entered = asyncio.Event()
    release_off = asyncio.Event()

    async def _delayed_on(*args: Any, **kwargs: Any) -> Any:
        on_entered.set()
        await release_on.wait()
        return await orig_on(*args, **kwargs)

    async def _delayed_off(*args: Any, **kwargs: Any) -> Any:
        off_entered.set()
        await release_off.wait()
        return await orig_off(*args, **kwargs)

    turn_on_context = Context(user_id=hass_admin_user.id, id="overlap_turn_on_ctx")
    turn_off_context = Context(user_id=hass_admin_user.id, id="overlap_turn_off_ctx")

    with (
        patch.object(group_on_off_cluster, "on", side_effect=_delayed_on),
        patch.object(group_on_off_cluster, "off", side_effect=_delayed_off),
    ):
        on_task = hass.async_create_task(
            hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: group_entity_id},
                blocking=True,
                context=turn_on_context,
            )
        )
        await on_entered.wait()

        # Issue turn_off (Context B) while turn_on (Context A) is still in flight
        off_task = hass.async_create_task(
            hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: group_entity_id},
                blocking=True,
                context=turn_off_context,
            )
        )
        await off_entered.wait()

        # Let the superseded turn_on (Context A) finish while turn_off (Context B) is still awaiting
        release_on.set()
        await on_task

        # Member reports off for Context B while turn_off is still awaiting
        cluster_1.update_attribute(general.OnOff.AttributeDefs.on_off.id, 0)

        release_off.set()
        await off_task

    member_1_state = hass.states.get(member_1_entity_id)
    assert member_1_state is not None
    assert member_1_state.state == STATE_OFF
    assert member_1_state.context == turn_off_context


async def test_group_entity_context_preserves_pending_context_on_mismatched_report(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a delayed report from an earlier command does not clear a newer pending group context."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    assert member_1_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off
    assert hass.states.get(member_1_entity_id).state == STATE_OFF

    turn_on_context = Context(user_id=hass_admin_user.id, id="seq_turn_on_ctx")
    turn_off_context = Context(user_id=hass_admin_user.id, id="seq_turn_off_ctx")

    # Command A: turn_on, followed immediately by Command B: turn_off before A's report arrives
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_on_context,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_off_context,
    )

    # Delayed report from A (on) arrives while B (expected off) is pending:
    # it must not inherit B's context, nor clear B's pending context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    member_1_on_state = hass.states.get(member_1_entity_id)
    assert member_1_on_state is not None
    assert member_1_on_state.state == STATE_ON
    assert member_1_on_state.context != turn_off_context

    # Matching report for B (off) then arrives and must still inherit B's context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    member_1_off_state = hass.states.get(member_1_entity_id)
    assert member_1_off_state is not None
    assert member_1_off_state.state == STATE_OFF
    assert member_1_off_state.context == turn_off_context


async def test_group_entity_context_invalidated_after_matched_opposing_transition(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an already-matched group context is invalidated after an opposing transition."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    assert member_1_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off

    turn_on_context = Context(user_id=hass_admin_user.id, id="matched_turn_on_ctx")
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=turn_on_context,
    )

    # Member matches the group turn_on command
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    member_1_on_state = hass.states.get(member_1_entity_id)
    assert member_1_on_state is not None
    assert member_1_on_state.state == STATE_ON
    assert member_1_on_state.context == turn_on_context

    # Physical off within 5 seconds must invalidate the matched group context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    member_1_off_state = hass.states.get(member_1_entity_id)
    assert member_1_off_state is not None
    assert member_1_off_state.state == STATE_OFF
    assert member_1_off_state.context != turn_on_context

    # Subsequent physical on within 5 seconds must not inherit the invalidated turn_on_context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    member_1_re_on_state = hass.states.get(member_1_entity_id)
    assert member_1_re_on_state is not None
    assert member_1_re_on_state.state == STATE_ON
    assert member_1_re_on_state.context != turn_on_context


@pytest.mark.usefixtures("zigpy_app_controller_with_group")
async def test_group_entity_context_light_level_command_skips_switch_members(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller: ControllerApplication,
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test light group commands using LevelControl do not propagate context to switches."""
    group = zigpy_app_controller.groups[FIXTURE_GRP_WITH_ENTITIES_ID]
    for ieee in ("01:2d:6f:00:0a:90:69:f1", "01:2d:6f:00:0a:90:69:f2"):
        light = zigpy_device_mock(
            {
                1: {
                    SIG_EP_INPUT: [
                        general.OnOff.cluster_id,
                        general.LevelControl.cluster_id,
                        general.Basic.cluster_id,
                        general.Groups.cluster_id,
                    ],
                    SIG_EP_OUTPUT: [],
                    SIG_EP_TYPE: zha.DeviceType.DIMMABLE_LIGHT,
                    SIG_EP_PROFILE: zha.PROFILE_ID,
                }
            },
            ieee=ieee,
        )
        zigpy_app_controller.devices[light.ieee] = light
        group.add_member(light.endpoints[1], suppress_event=True)

    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            zha_const.CUSTOM_CONFIGURATION: {
                zha_const.ZHA_OPTIONS: {
                    zha_const.CONF_ENABLE_LIGHT_TRANSITIONING_FLAG: False,
                    zha_const.CONF_GROUP_MEMBERS_ASSUME_STATE: False,
                },
            }
        },
    )
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    light_group_entity_id = entity_registry.async_get_entity_id(
        Platform.LIGHT,
        DOMAIN,
        f"light_zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
    )
    assert light_group_entity_id is not None

    light_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:f1")
    switch_1_ieee = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    light_1_id = find_entity_id(
        Platform.LIGHT, gateway_proxy.device_proxies[light_1_ieee], hass
    )
    switch_1_id = find_entity_id(
        Platform.SWITCH, gateway_proxy.device_proxies[switch_1_ieee], hass
    )
    assert light_1_id is not None
    assert switch_1_id is not None

    light_1_ep = zigpy_app_controller.devices[light_1_ieee].endpoints[1]
    switch_1_ep = zigpy_app_controller.devices[switch_1_ieee].endpoints[1]

    # turn_on with brightness uses LevelControl, so only light members should inherit context
    brightness_ctx = Context(user_id=hass_admin_user.id, id="light_brightness_ctx")
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_group_entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
        context=brightness_ctx,
    )

    await send_attributes_report(
        hass, light_1_ep.on_off, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    light_1_on_state = hass.states.get(light_1_id)
    assert light_1_on_state is not None
    assert light_1_on_state.state == STATE_ON
    assert light_1_on_state.context == brightness_ctx

    await send_attributes_report(
        hass, switch_1_ep.on_off, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    switch_1_on_state = hass.states.get(switch_1_id)
    assert switch_1_on_state is not None
    assert switch_1_on_state.state == STATE_ON
    assert switch_1_on_state.context != brightness_ctx

    # turn_off with transition also uses LevelControl, not OnOff
    transition_off_ctx = Context(
        user_id=hass_admin_user.id, id="light_transition_off_ctx"
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: light_group_entity_id, ATTR_TRANSITION: 2},
        blocking=True,
        context=transition_off_ctx,
    )

    await send_attributes_report(
        hass, light_1_ep.on_off, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    light_1_off_state = hass.states.get(light_1_id)
    assert light_1_off_state is not None
    assert light_1_off_state.state == STATE_OFF
    assert light_1_off_state.context == transition_off_ctx

    await send_attributes_report(
        hass, switch_1_ep.on_off, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    switch_1_off_state = hass.states.get(switch_1_id)
    assert switch_1_off_state is not None
    assert switch_1_off_state.state == STATE_OFF
    assert switch_1_off_state.context != transition_off_ctx


async def test_group_entity_context_noop_does_not_attribute_later_physical_toggle(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
    zigpy_app_controller_with_group: ControllerApplication,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a no-op group command does not attribute a later physical off-then-on toggle."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_WITH_ENTITIES_ID]
    assert group_proxy.device_id is not None

    [group_entry] = er.async_entries_for_device(entity_registry, group_proxy.device_id)
    group_entity_id = group_entry.entity_id

    ieee_1 = EUI64.convert("01:2d:6f:00:0a:90:69:e1")
    dev_proxy_1 = gateway_proxy.device_proxies[ieee_1]
    member_1_entity_id = find_entity_id(Platform.SWITCH, dev_proxy_1, hass)
    assert member_1_entity_id is not None

    cluster_1 = zigpy_app_controller_with_group.devices[ieee_1].endpoints[1].on_off
    # Member 1 starts on before the group turn_on no-op is sent
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    assert hass.states.get(member_1_entity_id).state == STATE_ON

    noop_turn_on_ctx = Context(user_id=hass_admin_user.id, id="noop_turn_on_ctx")
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
        context=noop_turn_on_ctx,
    )

    # Physical off within 5s must clear the already-satisfied no-op context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 0}
    )
    member_1_off_state = hass.states.get(member_1_entity_id)
    assert member_1_off_state is not None
    assert member_1_off_state.state == STATE_OFF
    assert member_1_off_state.context != noop_turn_on_ctx

    # Subsequent physical on within 5s must not inherit the no-op turn_on context
    await send_attributes_report(
        hass, cluster_1, {general.OnOff.AttributeDefs.on_off.id: 1}
    )
    member_1_on_state = hass.states.get(member_1_entity_id)
    assert member_1_on_state is not None
    assert member_1_on_state.state == STATE_ON
    assert member_1_on_state.context != noop_turn_on_ctx
