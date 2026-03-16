"""Test ZHA handling of runtime device entity added/removed events."""

from collections.abc import Callable, Coroutine
from unittest.mock import patch

import pytest
from zha.zigbee.device import DeviceEntityAddedEvent, DeviceEntityRemovedEvent
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import (
    SIGNAL_ADD_ENTITIES,
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_data,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import find_entity_id
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


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


async def _create_switch_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> tuple[ZHADeviceProxy, ZHAGatewayProxy, Device]:
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
    return zha_device_proxy, gateway_proxy, zigpy_device


async def test_handle_device_entity_added(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a runtime DeviceEntityAddedEvent populates platform data and dispatches signal."""
    zha_device_proxy, _, _ = await _create_switch_device(
        hass, setup_zha, zigpy_device_mock
    )

    # Get the switch platform entity from the ZHA device
    switch_entities = [
        entity
        for entity in zha_device_proxy.device.platform_entities.values()
        if entity.PLATFORM == Platform.SWITCH
    ]
    assert len(switch_entities) > 0
    platform_entity = switch_entities[0]

    ha_zha_data = get_zha_data(hass)

    # The platform entity list should be empty (cleared after initial entity creation)
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0

    # Listen for the add entities signal
    signal_calls: list[bool] = []

    @callback
    def _signal_listener() -> None:
        signal_calls.append(True)

    async_dispatcher_connect(hass, SIGNAL_ADD_ENTITIES, _signal_listener)

    # Fire the entity added event
    zha_device_proxy.handle_zha_device_entity_added_event(
        DeviceEntityAddedEvent(unique_id=platform_entity.unique_id)
    )

    # Verify the signal was dispatched
    assert len(signal_calls) == 1


async def test_handle_device_entity_added_unknown_unique_id(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a DeviceEntityAddedEvent with unknown unique_id is a no-op."""
    zha_device_proxy, _, _ = await _create_switch_device(
        hass, setup_zha, zigpy_device_mock
    )

    ha_zha_data = get_zha_data(hass)
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0

    signal_calls: list[bool] = []

    @callback
    def _signal_listener() -> None:
        signal_calls.append(True)

    async_dispatcher_connect(hass, SIGNAL_ADD_ENTITIES, _signal_listener)

    zha_device_proxy.handle_zha_device_entity_added_event(
        DeviceEntityAddedEvent(unique_id="nonexistent_unique_id")
    )

    # Nothing should be added and no signal dispatched
    assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0
    assert len(signal_calls) == 0


async def test_handle_device_entity_removed(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a runtime DeviceEntityRemovedEvent removes the HA entity."""
    zha_device_proxy, gateway_proxy, _ = await _create_switch_device(
        hass, setup_zha, zigpy_device_mock
    )

    # Verify entity exists
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    registry = er.async_get(hass)
    assert registry.async_get(entity_id) is not None

    # Get the unique_id of the platform entity backing this HA entity
    entity_refs = gateway_proxy.ha_entity_refs[zha_device_proxy.device.ieee]
    target_ref = next(ref for ref in entity_refs if ref.ha_entity_id == entity_id)
    target_unique_id = target_ref.entity_data.entity.unique_id

    # Fire the entity removed event
    zha_device_proxy.handle_zha_device_entity_removed_event(
        DeviceEntityRemovedEvent(unique_id=target_unique_id)
    )
    await hass.async_block_till_done()

    # Verify the entity was removed from the entity registry
    assert registry.async_get(entity_id) is None


async def test_handle_device_entity_removed_unknown_unique_id(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that a DeviceEntityRemovedEvent with unknown unique_id is a no-op."""
    zha_device_proxy, _, _ = await _create_switch_device(
        hass, setup_zha, zigpy_device_mock
    )

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    # Fire event with a unique_id that doesn't match any entity ref
    zha_device_proxy.handle_zha_device_entity_removed_event(
        DeviceEntityRemovedEvent(unique_id="nonexistent_unique_id")
    )
    await hass.async_block_till_done()

    # Verify the entity was NOT removed
    registry = er.async_get(hass)
    assert registry.async_get(entity_id) is not None
