"""Test ZHA entities."""

from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


async def test_device_registry_via_device(
    hass: HomeAssistant,
    setup_zha,
    zigpy_device_mock,
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
