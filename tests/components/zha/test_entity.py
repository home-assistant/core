"""Test ZHA entities."""

from collections.abc import Callable, Coroutine
from typing import Any

from zigpy.application import ControllerApplication
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import get_zha_gateway, get_zha_gateway_proxy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test ZHA `via_device` is set correctly."""

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

    reg_coordinator_device = device_registry.async_get_device(
        identifiers={("zha", str(gateway.state.node_info.ieee))}
    )

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
    )

    assert reg_device.via_device_id == reg_coordinator_device.id


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
    assert (
        "zha",
        f"zha_group_0x{FIXTURE_GRP_WITH_ENTITIES_ID:04x}",
    ) in device.identifiers
    assert device.manufacturer == "Zigbee"
    assert device.model == "Group"
    assert device.entry_type == dr.DeviceEntryType.SERVICE
