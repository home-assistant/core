"""Test ZHA handling of runtime device entity added/removed events."""

from collections.abc import Callable, Coroutine
from unittest.mock import patch

import pytest
from zha.application import Platform as ZhaPlatform
from zha.zigbee.device import DeviceEntityAddedEvent, DeviceEntityRemovedEvent
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
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

    # Fire the entity added event
    with patch(
        "homeassistant.components.zha.helpers.async_dispatcher_send"
    ) as mock_dispatch:
        zha_device_proxy.handle_zha_device_entity_added_event(
            DeviceEntityAddedEvent(
                platform=ZhaPlatform(platform_entity.PLATFORM),
                unique_id=platform_entity.unique_id,
            )
        )

        # Verify EntityData was appended to the platform list
        assert len(ha_zha_data.platforms[Platform.SWITCH]) == 1
        entity_data = ha_zha_data.platforms[Platform.SWITCH][0]
        assert entity_data.entity is platform_entity
        assert entity_data.device_proxy is zha_device_proxy
        assert entity_data.group_proxy is None

        # Verify SIGNAL_ADD_ENTITIES was dispatched
        mock_dispatch.assert_called_once_with(hass, "zha_add_entities")

    # Clean up
    ha_zha_data.platforms[Platform.SWITCH].clear()


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

    with patch(
        "homeassistant.components.zha.helpers.async_dispatcher_send"
    ) as mock_dispatch:
        zha_device_proxy.handle_zha_device_entity_added_event(
            DeviceEntityAddedEvent(
                platform=ZhaPlatform.SWITCH,
                unique_id="nonexistent_unique_id",
            )
        )

        # Nothing should be added and no signal dispatched
        assert len(ha_zha_data.platforms[Platform.SWITCH]) == 0
        mock_dispatch.assert_not_called()


async def test_handle_device_entity_removed(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that DeviceEntityRemovedEvent with remove=False only unloads the entity."""
    zha_device_proxy, _, _ = await _create_switch_device(
        hass, setup_zha, zigpy_device_mock
    )

    # Verify entity exists and has a state
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert hass.states.get(entity_id) is not None

    # Fire the entity removed event with remove=False
    zha_device_proxy.handle_zha_device_entity_removed_event(
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=entry.unique_id,
            remove=False,
        )
    )
    await hass.async_block_till_done()

    # The registry entry is preserved so the user can manually delete it
    assert registry.async_get(entity_id) is not None

    # The entity state is set to unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_handle_device_entity_removed_with_remove_flag(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test that DeviceEntityRemovedEvent with remove=True deletes the registry entry."""
    zha_device_proxy, _, _ = await _create_switch_device(
        hass, setup_zha, zigpy_device_mock
    )

    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert hass.states.get(entity_id) is not None

    # Fire the entity removed event with remove=True
    zha_device_proxy.handle_zha_device_entity_removed_event(
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id=entry.unique_id,
            remove=True,
        )
    )
    await hass.async_block_till_done()

    # The registry entry is removed
    assert registry.async_get(entity_id) is None

    # The entity state is also gone
    assert hass.states.get(entity_id) is None


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

    # Fire event with a unique_id that doesn't match any entity
    zha_device_proxy.handle_zha_device_entity_removed_event(
        DeviceEntityRemovedEvent(
            platform=ZhaPlatform.SWITCH,
            unique_id="nonexistent_unique_id",
        )
    )
    await hass.async_block_till_done()

    # Verify the entity was NOT removed
    registry = er.async_get(hass)
    assert registry.async_get(entity_id) is not None
