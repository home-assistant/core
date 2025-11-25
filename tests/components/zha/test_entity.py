"""Test ZHA entities."""

from collections.abc import Callable, Coroutine
from unittest.mock import patch

import pytest
from zigpy.device import Device
from zigpy.profiles import zha
import zigpy.types as t
from zigpy.zcl.clusters import general, measurement

from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ENTITY_ID_NO_PREFIX = "{}.fakemanufacturer_fakemodel"
ENTITY_ID_PREFIX_NUM = "{}.fakemanufacturer_fakemodel_{}_{}"


@pytest.fixture(autouse=True)
def sensor_and_switch_platform_only():
    """Only set up the switch and sensor platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.SENSOR,
            Platform.SWITCH,
        ),
    ):
        yield


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


@pytest.mark.parametrize(
    (
        "cluster_id",
        "entity_prefix",
        "entity_suffix",
    ),
    [
        (
            measurement.TemperatureMeasurement.cluster_id,
            "sensor",
            "temperature",
        ),
        (
            measurement.PressureMeasurement.cluster_id,
            "sensor",
            "pressure",
        ),
        (
            general.OnOff.cluster_id,
            "switch",
            "switch",
        ),
    ],
)
async def test_entity_postfix(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    cluster_id: t.uint16_t,
    entity_prefix: str,
    entity_suffix: str,
) -> None:
    """Test postfix when a device has several entities of the same type."""
    n_endpoints = 2

    await setup_zha()
    gateway = get_zha_gateway(hass)

    endpoint_definition = {
        SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
        SIG_EP_OUTPUT: [],
        SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
    }

    # Create a device with n_endpoints identical endpoints
    zigpy_device = zigpy_device_mock(
        dict.fromkeys(range(1, n_endpoints + 1), endpoint_definition),
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    for n in range(1, n_endpoints + 1):
        state = hass.states.get(
            ENTITY_ID_PREFIX_NUM.format(entity_prefix, entity_suffix, n)
        )
        assert state is not None
        assert state.name.endswith(f" ({n})")


@pytest.mark.parametrize(
    (
        "cluster_id",
        "entity_prefix",
    ),
    [
        (
            measurement.TemperatureMeasurement.cluster_id,
            "sensor",
        ),
        (
            measurement.PressureMeasurement.cluster_id,
            "sensor",
        ),
        (
            general.OnOff.cluster_id,
            "switch",
        ),
    ],
)
async def test_single_entity_no_postfix(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    cluster_id: t.uint16_t,
    entity_prefix: str,
) -> None:
    """Test that postfix is not in the name of singular entities."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
            },
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID_NO_PREFIX.format(entity_prefix))
    assert state is not None
    # Name should not be "Entity (<NUM>)", check for trailing parenthesis
    assert not state.name.endswith(")")
