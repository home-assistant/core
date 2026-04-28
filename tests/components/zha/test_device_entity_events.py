"""Test ZHA handling of runtime device entity added/removed events."""

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
    SIGNAL_ADD_ENTITIES,
    ZHADeviceProxy,
    get_zha_data,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def switch_platform_only() -> Generator[None]:
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


async def _create_switch_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> ZHADeviceProxy:
    """Create a basic switch device for testing."""
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
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
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


def _get_switch_platform_entity(zha_device_proxy: ZHADeviceProxy) -> PlatformEntity:
    """Return the underlying ZHA switch platform entity for the device."""
    return next(
        entity
        for entity in zha_device_proxy.device.platform_entities.values()
        if entity.PLATFORM == Platform.SWITCH
    )


async def test_handle_device_entity_added(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that DeviceEntityAddedEvent re-creates a previously removed entity."""
    zha_device_proxy = await _create_switch_device(hass, setup_zha, zigpy_device_mock)
    platform_entity = _get_switch_platform_entity(zha_device_proxy)
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    # Remove first so the re-add has visible side effects (state reappears).
    zha_device_proxy.device.emit(
        DeviceEntityRemovedEvent.event_type,
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=platform_entity.unique_id,
            remove=True,
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None

    ha_zha_data = get_zha_data(hass)
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0

    # Fire the entity-added event through the device emitter to exercise
    # the on_all_events -> _handle_event_protocol -> handler wiring.
    zha_device_proxy.device.emit(
        DeviceEntityAddedEvent.event_type,
        DeviceEntityAddedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=platform_entity.unique_id,
        ),
    )
    await hass.async_block_till_done()

    # The platform list is drained by SIGNAL_ADD_ENTITIES handler.
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0

    # The entity is back and reachable as a HA state.
    assert hass.states.get(entity_id) is not None

    # Exactly one entity reference is recorded for this entity_id (no stale
    # leftovers from the remove + re-add cycle).
    gateway_proxy = get_zha_gateway_proxy(hass)
    matching_refs = [
        ref
        for ref in gateway_proxy.ha_entity_refs[zha_device_proxy.device.ieee]
        if ref.ha_entity_id == entity_id
    ]
    assert len(matching_refs) == 1


async def test_handle_device_entity_added_unknown_unique_id(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a DeviceEntityAddedEvent with unknown unique_id is a no-op."""
    zha_device_proxy = await _create_switch_device(hass, setup_zha, zigpy_device_mock)

    ha_zha_data = get_zha_data(hass)
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0

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

        # Nothing should be added and SIGNAL_ADD_ENTITIES is never dispatched.
        assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0
        for call in mock_dispatch.call_args_list:
            assert call.args != (hass, SIGNAL_ADD_ENTITIES)


async def test_handle_device_entity_removed(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that DeviceEntityRemovedEvent with remove=False only unloads the entity."""
    zha_device_proxy = await _create_switch_device(hass, setup_zha, zigpy_device_mock)

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert hass.states.get(entity_id) is not None

    # Fire through the device emitter so the on_all_events wiring is exercised.
    zha_device_proxy.device.emit(
        DeviceEntityRemovedEvent.event_type,
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=entry.unique_id,
            remove=False,
        ),
    )
    await hass.async_block_till_done()

    # Registry entry preserved so the user can manually delete it.
    assert registry.async_get(entity_id) is not None

    # State is set to unavailable.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_handle_device_entity_removed_with_remove_flag(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that DeviceEntityRemovedEvent with remove=True deletes the registry entry."""
    zha_device_proxy = await _create_switch_device(hass, setup_zha, zigpy_device_mock)

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert hass.states.get(entity_id) is not None

    zha_device_proxy.device.emit(
        DeviceEntityRemovedEvent.event_type,
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=entry.unique_id,
            remove=True,
        ),
    )
    await hass.async_block_till_done()

    # Registry entry and state are both gone.
    assert registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None

    # No stale entity reference is left in the gateway proxy.
    gateway_proxy = get_zha_gateway_proxy(hass)
    assert all(
        ref.ha_entity_id != entity_id
        for ref in gateway_proxy.ha_entity_refs[zha_device_proxy.device.ieee]
    )


async def test_handle_device_entity_removed_unknown_unique_id(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a DeviceEntityRemovedEvent with unknown unique_id is a no-op."""
    zha_device_proxy = await _create_switch_device(hass, setup_zha, zigpy_device_mock)

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

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

        # The original entity is untouched.
        registry = er.async_get(hass)
        assert registry.async_get(entity_id) is not None
        assert hass.states.get(entity_id) is not None
