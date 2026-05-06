"""Test ZHA dynamic entity lifecycle (runtime add/remove and reference cleanup)."""

from collections.abc import Callable, Coroutine, Generator
from unittest.mock import patch

import pytest
from zha.application import Platform as ZhaPlatform
from zha.application.platforms import PlatformEntity
from zha.zigbee.device import DeviceEntityAddedEvent, DeviceEntityRemovedEvent
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    get_zha_data,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def platforms_only() -> Generator[None]:
    """Only set up the switch + binary_sensor platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (Platform.SWITCH, Platform.BINARY_SENSOR),
    ):
        yield


async def _create_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> ZHADeviceProxy:
    """Create a device exposing a switch and a binary_sensor that share a unique_id.

    OnOff input on an occupancy-sensor device type yields a switch entity
    and a binary_sensor entity (Opening) keyed on the same `(ieee, ep, 6)`
    base unique_id but on different platforms - a useful collision shape
    for verifying that runtime add/remove events are scoped per platform.
    """
    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.OnOff.cluster_id,
                    general.Groups.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.OCCUPANCY_SENSOR,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    assert zha_device_proxy is not None
    return zha_device_proxy


def _get_platform_entity(
    zha_device_proxy: ZHADeviceProxy, platform: Platform
) -> PlatformEntity:
    """Return the underlying ZHA platform entity for the given platform."""
    return next(
        entity
        for entity in zha_device_proxy.device.platform_entities.values()
        if platform == entity.PLATFORM
    )


async def test_dynamic_entity_lifecycle(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test the full hard-remove -> re-add -> soft-remove cycle.

    Also confirms that the binary_sensor sharing the same unique_id but on a
    different platform is never disturbed - the (platform, unique_id) tuple
    is the ZHA entity identity.
    """
    zha_device_proxy = await _create_device(hass, setup_zha, zigpy_device_mock)
    platform_entity = _get_platform_entity(zha_device_proxy, Platform.SWITCH)
    binary_sensor_entity = _get_platform_entity(
        zha_device_proxy, Platform.BINARY_SENSOR
    )
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    binary_sensor_id = find_entity_id(Platform.BINARY_SENSOR, zha_device_proxy, hass)
    assert entity_id is not None
    assert binary_sensor_id is not None

    # Same unique_id, different platforms - the collision shape we care about.
    assert platform_entity.unique_id == binary_sensor_entity.unique_id
    assert platform_entity.PLATFORM != binary_sensor_entity.PLATFORM

    switch_state_before = hass.states.get(entity_id)
    binary_sensor_state_before = hass.states.get(binary_sensor_id)
    assert switch_state_before is not None
    assert switch_state_before.state == STATE_OFF
    assert binary_sensor_state_before is not None
    assert binary_sensor_state_before.state == STATE_OFF

    # Hard remove: state and registry entry both go away.
    zha_device_proxy.device.emit(
        DeviceEntityRemovedEvent.event_type,
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=platform_entity.unique_id,
            remove=True,
        ),
    )
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None
    # The binary_sensor with the same unique_id is untouched.
    assert registry.async_get(binary_sensor_id) is not None
    assert hass.states.get(binary_sensor_id) == binary_sensor_state_before

    ha_zha_data = get_zha_data(hass)
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0

    # Re-add: emitter exercises the on_all_events -> _handle_event_protocol
    # -> handler wiring; the entity reappears as a HA state.
    zha_device_proxy.device.emit(
        DeviceEntityAddedEvent.event_type,
        DeviceEntityAddedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=platform_entity.unique_id,
        ),
    )
    await hass.async_block_till_done()
    # The platform listener drained the queue when SIGNAL_ADD_ENTITIES fired.
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0
    switch_state_after = hass.states.get(entity_id)
    assert switch_state_after is not None
    assert switch_state_after.state == switch_state_before.state
    assert hass.states.get(binary_sensor_id) == binary_sensor_state_before

    # Exactly one entity reference is tracked; the remove + re-add cycle did
    # not leave a stale entry behind.
    gateway_proxy = get_zha_gateway_proxy(hass)
    matching_refs = [
        ref
        for ref in gateway_proxy.ha_entity_refs[zha_device_proxy.device.ieee]
        if ref.ha_entity_id == entity_id
    ]
    assert len(matching_refs) == 1

    # Soft remove: registry entry is kept, state goes unavailable.
    entry = registry.async_get(entity_id)
    assert entry is not None
    zha_device_proxy.device.emit(
        DeviceEntityRemovedEvent.event_type,
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=entry.unique_id,
            remove=False,
        ),
    )
    await hass.async_block_till_done()
    assert registry.async_get(entity_id) is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    # The binary_sensor with the same unique_id is still untouched.
    assert hass.states.get(binary_sensor_id) == binary_sensor_state_before


async def test_unknown_unique_id_is_noop(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that add/remove events with an unknown unique_id are no-ops."""
    zha_device_proxy = await _create_device(hass, setup_zha, zigpy_device_mock)

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    ha_zha_data = get_zha_data(hass)
    registry = er.async_get(hass)

    # Added: nothing queued, no dispatcher signal fired.
    with patch(
        "homeassistant.components.zha.helpers.async_dispatcher_send"
    ) as mock_dispatch:
        zha_device_proxy.device.emit(
            DeviceEntityAddedEvent.event_type,
            DeviceEntityAddedEvent(
                platform=ZhaPlatform.SWITCH,
                unique_id="nonexistent_unique_id",
            ),
        )
        await hass.async_block_till_done()

        assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0
        mock_dispatch.assert_not_called()

    # Removed (both flag values): the existing entity is untouched.
    for remove in (False, True):
        zha_device_proxy.device.emit(
            DeviceEntityRemovedEvent.event_type,
            DeviceEntityRemovedEvent(
                platform=ZhaPlatform.SWITCH,
                unique_id="nonexistent_unique_id",
                remove=remove,
            ),
        )
        await hass.async_block_till_done()

        assert registry.async_get(entity_id) is not None
        assert hass.states.get(entity_id) is not None


async def test_remove_entity_reference_when_ieee_already_cleared(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test entity teardown when _ha_entity_refs already lost the ieee.

    Simulates the race where ``handle_device_removed`` pops the ieee entry
    before the entity finishes tearing down. The early-return guard must
    keep the popped key out of the dict.
    """
    zha_device_proxy = await _create_device(hass, setup_zha, zigpy_device_mock)

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    gateway_proxy = get_zha_gateway_proxy(hass)
    ieee = zha_device_proxy.device.ieee
    gateway_proxy._ha_entity_refs.pop(ieee, None)

    er.async_get(hass).async_remove(entity_id)
    await hass.async_block_till_done()

    assert ieee not in gateway_proxy._ha_entity_refs
