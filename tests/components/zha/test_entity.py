"""Test ZHA entities."""

from collections.abc import Callable, Coroutine
from unittest.mock import MagicMock

from zha.application.platforms import GroupEntity
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.entity import ZHAEntity
from homeassistant.components.zha.helpers import (
    EntityData,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    FIXTURE_GRP_ID,
    FIXTURE_GRP_NAME,
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


async def test_group_without_entities_has_no_separate_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test ZHA group without entities does not create an empty device."""

    await setup_zha()
    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_ID]

    assert group_proxy.device_id is None
    assert (
        device_registry.async_get_device(
            identifiers={("zha", group_proxy.device_identifier)}
        )
        is None
    )


async def test_group_entity_uses_group_device_info(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test ZHA group entity is associated with the group device."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy = get_zha_gateway_proxy(hass)
    group_proxy = gateway_proxy.group_proxies[FIXTURE_GRP_ID]
    coordinator_proxy = gateway_proxy.device_proxies[
        gateway_proxy.gateway.coordinator_zha_device.ieee
    ]

    group_entity = MagicMock(spec=GroupEntity)
    group_entity.PLATFORM = Platform.SWITCH
    group_entity.icon = None
    group_entity.info_object.unique_id = "switch_zha_group_0x1001"
    group_entity.info_object.entity_category = None
    group_entity.info_object.entity_registry_enabled_default = True
    group_entity.info_object.translation_key = None
    group_entity.info_object.translation_placeholders = None

    entity = ZHAEntity(
        EntityData(
            entity=group_entity,
            device_proxy=coordinator_proxy,
            group_proxy=group_proxy,
        )
    )

    assert entity.device_info == group_proxy.device_info

    reg_coordinator_device = device_registry.async_get_device(
        identifiers={("zha", str(gateway.state.node_info.ieee))}
    )
    reg_group_device = device_registry.async_get_or_create(
        config_entry_id=gateway_proxy.config_entry.entry_id,
        **entity.device_info,
    )
    remove_future = hass.loop.create_future()
    gateway_proxy.register_entity_reference(
        "switch.test_group",
        entity.entity_data,
        entity.device_info,
        remove_future,
    )

    assert reg_coordinator_device is not None
    assert reg_group_device.name == FIXTURE_GRP_NAME
    assert reg_group_device.identifiers == {("zha", group_proxy.device_identifier)}
    assert reg_group_device.via_device_id == reg_coordinator_device.id
    assert group_proxy.device_id == reg_group_device.id
