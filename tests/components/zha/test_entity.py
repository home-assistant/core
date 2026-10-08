"""Test ZHA entities."""

from collections.abc import Callable, Coroutine

from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.const import DOMAIN
from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import MockConfigEntry


async def test_device_registry_via_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
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
    zigpy_device_mock: Callable[..., Device],
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
