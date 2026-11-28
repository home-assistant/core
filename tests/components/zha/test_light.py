"""Test ZHA light."""

from collections.abc import Callable, Coroutine
from unittest.mock import AsyncMock, call, patch, sentinel

import pytest
from pytest_homeassistant.common import mock_restore_cache
from zha.application.platforms.light.const import FLASH_EFFECTS
from zigpy.device import ZigbeeDevice
from zigpy.profiles import zha
from zigpy.zcl import Cluster
from zigpy.zcl.clusters import general, lighting
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    FLASH_LONG,
    FLASH_SHORT,
    ColorMode,
)
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr

from .common import (
    async_shift_time,
    find_entity_id,
    send_attributes_report,
    update_attribute_cache,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

LIGHT_ON_OFF = {
    1: {
        SIG_EP_PROFILE: zha.PROFILE_ID,
        SIG_EP_TYPE: zha.DeviceType.ON_OFF_LIGHT,
        SIG_EP_INPUT: [
            general.Basic.cluster_id,
            general.Identify.cluster_id,
            general.OnOff.cluster_id,
        ],
        SIG_EP_OUTPUT: [general.Ota.cluster_id],
    }
}

LIGHT_LEVEL = {
    1: {
        SIG_EP_PROFILE: zha.PROFILE_ID,
        SIG_EP_TYPE: zha.DeviceType.DIMMABLE_LIGHT,
        SIG_EP_INPUT: [
            general.Basic.cluster_id,
            general.LevelControl.cluster_id,
            general.OnOff.cluster_id,
        ],
        SIG_EP_OUTPUT: [general.Ota.cluster_id],
    }
}

LIGHT_COLOR = {
    1: {
        SIG_EP_PROFILE: zha.PROFILE_ID,
        SIG_EP_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
        SIG_EP_INPUT: [
            general.Basic.cluster_id,
            general.Identify.cluster_id,
            general.LevelControl.cluster_id,
            general.OnOff.cluster_id,
            lighting.Color.cluster_id,
        ],
        SIG_EP_OUTPUT: [general.Ota.cluster_id],
    }
}


@pytest.fixture(autouse=True)
def light_platform_only():
    """Only set up the light and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.DEVICE_TRACKER,
            Platform.BUTTON,
            Platform.LIGHT,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.SELECT,
        ),
    ):
        yield


@patch(
    "zigpy.zcl.clusters.lighting.Color.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.Identify.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.LevelControl.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.OnOff.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@pytest.mark.parametrize(
    ("device", "reporting"),
    [(LIGHT_ON_OFF, (1, 0, 0)), (LIGHT_LEVEL, (1, 1, 0)), (LIGHT_COLOR, (1, 1, 6))],
)
async def test_light(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    device,
    reporting,
) -> None:
    """Test ZHA light platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(device)
    cluster_color = getattr(zigpy_device.endpoints[1], "light_color", None)

    if cluster_color:
        cluster_color.PLUGGED_ATTR_READS = {
            "color_temperature": 100,
            "color_temp_physical_min": 0,
            "color_temp_physical_max": 600,
            "color_capabilities": lighting.ColorCapabilities.XY_attributes
            | lighting.ColorCapabilities.Color_temperature,
        }
        update_attribute_cache(cluster_color)

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.LIGHT, zha_device_proxy, hass)
    assert entity_id is not None

    cluster_on_off = zigpy_device.endpoints[1].on_off
    cluster_level = getattr(zigpy_device.endpoints[1], "level", None)
    cluster_identify = getattr(zigpy_device.endpoints[1], "identify", None)

    assert hass.states.get(entity_id).state == STATE_OFF

    # test turning the lights on and off from the light
    await async_test_on_off_from_light(hass, cluster_on_off, entity_id)

    # test turning the lights on and off from the HA
    await async_test_on_off_from_hass(hass, cluster_on_off, entity_id)

    # test short flashing the lights from the HA
    if cluster_identify:
        await async_test_flash_from_hass(hass, cluster_identify, entity_id, FLASH_SHORT)

    # test long flashing the lights from the HA
    if cluster_identify:
        await async_test_flash_from_hass(hass, cluster_identify, entity_id, FLASH_LONG)

    # test dimming the lights on and off from the HA
    if cluster_level:
        await async_test_level_on_off_from_hass(
            hass, cluster_on_off, cluster_level, entity_id
        )
        await async_shift_time(hass)

        # test getting a brightness change from the network
        await async_test_on_from_light(hass, cluster_on_off, entity_id)
        await async_test_dimmer_from_light(
            hass, cluster_level, entity_id, 150, STATE_ON
        )


@patch(
    "zigpy.zcl.clusters.lighting.Color.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.LevelControl.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.OnOff.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_on_with_off_color(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test color commands sent before on/level for supporting lights."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.OnOff.cluster_id,
                    general.LevelControl.cluster_id,
                    lighting.Color.cluster_id,
                    general.Groups.cluster_id,
                    general.Identify.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        nwk=0xB79D,
    )

    dev1_cluster_color = zigpy_device.endpoints[1].light_color

    dev1_cluster_color.PLUGGED_ATTR_READS = {
        "color_capabilities": lighting.Color.ColorCapabilities.Color_temperature
        | lighting.Color.ColorCapabilities.XY_attributes
    }

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.LIGHT, zha_device_proxy, hass)
    assert entity_id is not None

    device_1_entity_id = find_entity_id(Platform.LIGHT, zha_device_proxy, hass)
    dev1_cluster_on_off = zigpy_device.endpoints[1].on_off
    dev1_cluster_level = zigpy_device.endpoints[1].level

    # Execute_if_off will override the "enhanced turn on from an
    # off-state" config option that's enabled here
    dev1_cluster_color.PLUGGED_ATTR_READS = {
        "options": lighting.Color.Options.Execute_if_off
    }
    update_attribute_cache(dev1_cluster_color)

    # turn on via UI
    dev1_cluster_on_off.request.reset_mock()
    dev1_cluster_level.request.reset_mock()
    dev1_cluster_color.request.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            "entity_id": device_1_entity_id,
            "color_temp_kelvin": 4255,
        },
        blocking=True,
    )

    assert dev1_cluster_on_off.request.call_count == 1
    assert dev1_cluster_on_off.request.await_count == 1
    assert dev1_cluster_color.request.call_count == 1
    assert dev1_cluster_color.request.await_count == 1
    assert dev1_cluster_level.request.call_count == 0
    assert dev1_cluster_level.request.await_count == 0

    assert dev1_cluster_on_off.request.call_args_list[0] == call(
        False,
        dev1_cluster_on_off.commands_by_name["on"].id,
        dev1_cluster_on_off.commands_by_name["on"].schema,
        expect_reply=True,
        manufacturer=None,
    )
    assert dev1_cluster_color.request.call_args == call(
        False,
        dev1_cluster_color.commands_by_name["move_to_color_temp"].id,
        dev1_cluster_color.commands_by_name["move_to_color_temp"].schema,
        color_temp_mireds=235,
        transition_time=0,
        expect_reply=True,
        manufacturer=None,
    )

    light1_state = hass.states.get(device_1_entity_id)
    assert light1_state.state == STATE_ON
    assert light1_state.attributes["color_temp_kelvin"] == 4255
    assert light1_state.attributes["color_mode"] == ColorMode.COLOR_TEMP

    # now let's turn off Execute_if_off and see if old behavior
    # is restored
    dev1_cluster_color.PLUGGED_ATTR_READS = {"options": 0}
    update_attribute_cache(dev1_cluster_color)

    # turn off via UI, so the old "enhanced turn on from an
    # off-state" behavior can do something
    await async_test_off_from_hass(hass, dev1_cluster_on_off, device_1_entity_id)

    # turn on via UI (with a different color temp, so the
    # "enhanced turn on" does something)
    dev1_cluster_on_off.request.reset_mock()
    dev1_cluster_level.request.reset_mock()
    dev1_cluster_color.request.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            "entity_id": device_1_entity_id,
            "color_temp_kelvin": 4166,
        },
        blocking=True,
    )

    assert dev1_cluster_on_off.request.call_count == 0
    assert dev1_cluster_on_off.request.await_count == 0
    assert dev1_cluster_color.request.call_count == 1
    assert dev1_cluster_color.request.await_count == 1
    assert dev1_cluster_level.request.call_count == 2
    assert dev1_cluster_level.request.await_count == 2

    # first it comes on with no transition at 2 brightness
    assert dev1_cluster_level.request.call_args_list[0] == call(
        False,
        dev1_cluster_level.commands_by_name["move_to_level_with_on_off"].id,
        dev1_cluster_level.commands_by_name["move_to_level_with_on_off"].schema,
        level=2,
        transition_time=0,
        expect_reply=True,
        manufacturer=None,
    )
    assert dev1_cluster_color.request.call_args == call(
        False,
        dev1_cluster_color.commands_by_name["move_to_color_temp"].id,
        dev1_cluster_color.commands_by_name["move_to_color_temp"].schema,
        color_temp_mireds=240,
        transition_time=0,
        expect_reply=True,
        manufacturer=None,
    )
    assert dev1_cluster_level.request.call_args_list[1] == call(
        False,
        dev1_cluster_level.commands_by_name["move_to_level"].id,
        dev1_cluster_level.commands_by_name["move_to_level"].schema,
        level=254,
        transition_time=0,
        expect_reply=True,
        manufacturer=None,
    )

    light1_state = hass.states.get(device_1_entity_id)
    assert light1_state.state == STATE_ON
    assert light1_state.attributes["brightness"] == 254
    assert light1_state.attributes["color_temp_kelvin"] == 4166
    assert light1_state.attributes["color_mode"] == ColorMode.COLOR_TEMP


async def async_test_on_off_from_light(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test on off functionality from the light."""
    # turn on at light
    await send_attributes_report(hass, cluster, {1: 0, 0: 1, 2: 3})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at light
    await send_attributes_report(hass, cluster, {1: 1, 0: 0, 2: 3})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_OFF


async def async_test_on_from_light(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test on off functionality from the light."""
    # turn on at light
    await send_attributes_report(hass, cluster, {1: -1, 0: 1, 2: 2})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_ON


async def async_test_on_off_from_hass(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test on off functionality from hass."""
    # turn on via UI
    cluster.request.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert cluster.request.call_count == 1
    assert cluster.request.await_count == 1
    assert cluster.request.call_args == call(
        False,
        cluster.commands_by_name["on"].id,
        cluster.commands_by_name["on"].schema,
        expect_reply=True,
        manufacturer=None,
    )

    await async_test_off_from_hass(hass, cluster, entity_id)


async def async_test_off_from_hass(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test turning off the light from Home Assistant."""

    # turn off via UI
    cluster.request.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert cluster.request.call_count == 1
    assert cluster.request.await_count == 1
    assert cluster.request.call_args == call(
        False,
        cluster.commands_by_name["off"].id,
        cluster.commands_by_name["off"].schema,
        expect_reply=True,
        manufacturer=None,
    )


async def async_test_level_on_off_from_hass(
    hass: HomeAssistant,
    on_off_cluster: Cluster,
    level_cluster: Cluster,
    entity_id: str,
    expected_default_transition: int = 0,
):
    """Test on off functionality from hass."""

    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()
    await async_shift_time(hass)

    # turn on via UI
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert on_off_cluster.request.call_count == 1
    assert on_off_cluster.request.await_count == 1
    assert level_cluster.request.call_count == 0
    assert level_cluster.request.await_count == 0
    assert on_off_cluster.request.call_args == call(
        False,
        on_off_cluster.commands_by_name["on"].id,
        on_off_cluster.commands_by_name["on"].schema,
        expect_reply=True,
        manufacturer=None,
    )
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await async_shift_time(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, "transition": 10},
        blocking=True,
    )
    assert on_off_cluster.request.call_count == 0
    assert on_off_cluster.request.await_count == 0
    assert level_cluster.request.call_count == 1
    assert level_cluster.request.await_count == 1
    assert level_cluster.request.call_args == call(
        False,
        level_cluster.commands_by_name["move_to_level_with_on_off"].id,
        level_cluster.commands_by_name["move_to_level_with_on_off"].schema,
        level=254,
        transition_time=100,
        expect_reply=True,
        manufacturer=None,
    )
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, "brightness": 10},
        blocking=True,
    )
    # the onoff cluster is now not used when brightness is present by default
    assert on_off_cluster.request.call_count == 0
    assert on_off_cluster.request.await_count == 0
    assert level_cluster.request.call_count == 1
    assert level_cluster.request.await_count == 1
    assert level_cluster.request.call_args == call(
        False,
        level_cluster.commands_by_name["move_to_level_with_on_off"].id,
        level_cluster.commands_by_name["move_to_level_with_on_off"].schema,
        level=10,
        transition_time=int(expected_default_transition),
        expect_reply=True,
        manufacturer=None,
    )
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await async_test_off_from_hass(hass, on_off_cluster, entity_id)


async def async_test_dimmer_from_light(
    hass: HomeAssistant,
    cluster: Cluster,
    entity_id: str,
    level: int,
    expected_state: str,
):
    """Test dimmer functionality from the light."""

    await send_attributes_report(
        hass, cluster, {1: level + 10, 0: level, 2: level - 10 or 22}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == expected_state
    # hass uses None for brightness of 0 in state attributes
    if level == 0:
        level = None
    assert hass.states.get(entity_id).attributes.get("brightness") == level


async def async_test_flash_from_hass(
    hass: HomeAssistant, cluster: Cluster, entity_id: str, flash
):
    """Test flash functionality from hass."""
    # turn on via UI
    cluster.request.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, "flash": flash},
        blocking=True,
    )
    assert cluster.request.call_count == 1
    assert cluster.request.await_count == 1
    assert cluster.request.call_args == call(
        False,
        cluster.commands_by_name["trigger_effect"].id,
        cluster.commands_by_name["trigger_effect"].schema,
        effect_id=FLASH_EFFECTS[flash],
        effect_variant=general.Identify.EffectVariant.Default,
        expect_reply=True,
        manufacturer=None,
    )


@pytest.mark.parametrize(
    "restored_color_mode",
    [
        # A mode written by another integration (e.g. Zigbee2MQTT)
        "hs",
        # Not a ColorMode at all
        "not_a_color_mode",
    ],
)
async def test_light_restore_unknown_color_mode(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    restored_color_mode: str,
) -> None:
    """A restored color_mode ZHA cannot map must not break entity setup."""
    entity_id = "light.fakemanufacturer_fakemodel"
    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                STATE_ON,
                {"color_mode": restored_color_mode},
            )
        ],
    )

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(LIGHT_COLOR)
    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None


async def test_light_restore_failure_leaves_no_stale_references(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """A restore failure must not leave signals or entity references behind.

    If restore ran after registration, the registered remove_future would
    never resolve and device removal would hang waiting on it.
    """
    entity_id = "light.fakemanufacturer_fakemodel"
    mock_restore_cache(hass, [State(entity_id, STATE_ON)])

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(LIGHT_COLOR)
    gateway.get_or_create_device(zigpy_device)
    with patch(
        "homeassistant.components.zha.light.Light.restore_external_state_attributes",
        side_effect=KeyError("boom"),
    ):
        await gateway.async_device_initialized(zigpy_device)
        await hass.async_block_till_done(wait_background_tasks=True)

    # The entity never finished adding
    assert hass.states.get(entity_id) is None

    # Device removal still completes; nothing was registered for the
    # failed entity, so no remove_future is left pending
    zha_device_proxy: ZHADeviceProxy = get_zha_gateway_proxy(hass).get_device_proxy(
        zigpy_device.ieee
    )
    gateway.device_removed(zha_device_proxy.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(zha_device_proxy.device_id) is None


@patch(
    "zigpy.zcl.clusters.lighting.Color.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.Identify.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.LevelControl.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@patch(
    "zigpy.zcl.clusters.general.OnOff.request",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_light_exception_on_creation(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ZHA light entity creation exception."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    zigpy_device = zigpy_device_mock(LIGHT_COLOR)

    gateway.get_or_create_device(zigpy_device)
    with patch(
        "homeassistant.components.zha.light.Light.__init__", side_effect=Exception
    ):
        await gateway.async_device_initialized(zigpy_device)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert "Error while adding entity from entity data" in caplog.text
