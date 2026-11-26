"""Tests for the ZHA services."""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, _Call, call, patch

import pytest
from zha.zigbee.device import BaseDevice
from zigpy.device import GreenPowerDevice as ZigpyGreenPowerDevice, ZigbeeDevice
import zigpy.exceptions
from zigpy.profiles import zha
from zigpy.typing import UNDEFINED as ZIGPY_UNDEFINED
from zigpy.zcl.clusters import general, security
from zigpy.zgp.types import ApplicationID, SrcID

from homeassistant.components.zha.const import DOMAIN, ZHAService
from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from .conftest import (
    FIXTURE_GRP_ID,
    SIG_EP_INPUT,
    SIG_EP_OUTPUT,
    SIG_EP_PROFILE,
    SIG_EP_TYPE,
)

if TYPE_CHECKING:
    from zigpy.application import ControllerApplication

IEEE_SWITCH_DEVICE = "01:2d:6f:00:0a:90:69:e7"
SET_ATTRIBUTE_DATA = {"endpoint_id": 1, "cluster_id": 6, "attribute": 0, "value": 1}
CLUSTER_COMMAND_DATA = {
    "endpoint_id": 1,
    "cluster_id": 6,
    "command": 0,
    "command_type": "server",
    "params": {},
}


def _add_switch_device(
    hass: HomeAssistant, zigpy_device_mock: Callable[..., ZigbeeDevice]
) -> BaseDevice:
    """Add an on/off switch device to the gateway and return the ZHA device."""
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, general.OnOff.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee=IEEE_SWITCH_DEVICE,
    )
    return get_zha_gateway(hass).get_or_create_device(zigpy_device)


async def test_services_registered_without_gateway(hass: HomeAssistant) -> None:
    """Test the actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    for service in (
        ZHAService.PERMIT,
        ZHAService.REMOVE,
        ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
        ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
        ZHAService.WARNING_DEVICE_SQUAWK,
        ZHAService.WARNING_DEVICE_WARN,
    ):
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(ZHAService.PERMIT, {}, id="permit"),
        pytest.param(ZHAService.REMOVE, {"ieee": IEEE_SWITCH_DEVICE}, id="remove"),
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            {
                "ieee": IEEE_SWITCH_DEVICE,
                "endpoint_id": 1,
                "cluster_id": 6,
                "attribute": 0,
                "value": 1,
            },
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {
                "ieee": IEEE_SWITCH_DEVICE,
                "endpoint_id": 1,
                "cluster_id": 6,
                "command": 0,
                "command_type": "server",
                "params": {},
            },
            id="issue_zigbee_cluster_command",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
            {"group": 1, "cluster_id": 6, "command": 0},
            id="issue_zigbee_group_command",
        ),
        pytest.param(
            ZHAService.WARNING_DEVICE_SQUAWK,
            {"ieee": IEEE_SWITCH_DEVICE},
            id="warning_device_squawk",
        ),
        pytest.param(
            ZHAService.WARNING_DEVICE_WARN,
            {"ieee": IEEE_SWITCH_DEVICE},
            id="warning_device_warn",
        ),
    ],
)
async def test_service_without_gateway_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise a user-facing error when no gateway is loaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "no_gateway"


@pytest.mark.parametrize(
    ("service", "data", "method", "expected_call"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            "write_zigbee_attribute",
            call(1, 6, 0, 1, cluster_type="in", manufacturer=ZIGPY_UNDEFINED),
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {**CLUSTER_COMMAND_DATA, "manufacturer": 0x1234},
            "issue_cluster_command",
            call(1, 6, 0, "server", None, {}, cluster_type="in", manufacturer=0x1234),
            id="issue_zigbee_cluster_command",
        ),
    ],
)
async def test_cluster_service(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    service: str,
    data: dict,
    method: str,
    expected_call: _Call,
) -> None:
    """Test the cluster actions are forwarded to the device."""
    await setup_zha()
    zha_device = _add_switch_device(hass, zigpy_device_mock)

    with patch.object(zha_device, method, AsyncMock()) as method_mock:
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE, **data}, blocking=True
        )

    assert method_mock.await_args_list == [expected_call]


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            CLUSTER_COMMAND_DATA,
            id="issue_zigbee_cluster_command",
        ),
        pytest.param(ZHAService.WARNING_DEVICE_SQUAWK, {}, id="warning_device_squawk"),
        pytest.param(ZHAService.WARNING_DEVICE_WARN, {}, id="warning_device_warn"),
    ],
)
async def test_service_unknown_device_raises(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    service: str,
    data: dict,
) -> None:
    """Test the device actions reject an unknown device."""
    await setup_zha()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE, **data}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "device_not_found"
    assert err.value.translation_placeholders == {"ieee": IEEE_SWITCH_DEVICE}


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            CLUSTER_COMMAND_DATA,
            id="issue_zigbee_cluster_command",
        ),
    ],
)
async def test_cluster_service_green_power_device_raises(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    service: str,
    data: dict,
) -> None:
    """Test the cluster actions reject a Green Power device."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_gpd = ZigpyGreenPowerDevice(
        gateway.application_controller,
        application_id=ApplicationID.SrcID,
        src_id=SrcID(0x12345678),
    )
    gateway.application_controller.devices[zigpy_gpd.ieee] = zigpy_gpd
    gateway.get_or_create_device(zigpy_gpd)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {"ieee": str(zigpy_gpd.ieee), **data}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_zigbee_device"
    assert err.value.translation_placeholders == {"ieee": str(zigpy_gpd.ieee)}


@pytest.mark.parametrize(
    ("side_effect", "message"),
    [
        pytest.param(
            zigpy.exceptions.DeliveryError(
                "Failed to deliver packet: <TXStatus.MAC_CHANNEL_ACCESS_FAILURE: 225>",
                225,
            ),
            (
                "Failed to send request: Failed to deliver packet: "
                "<TXStatus.MAC_CHANNEL_ACCESS_FAILURE: 225>"
            ),
            id="delivery_error",
        ),
        pytest.param(
            TimeoutError(),
            "Failed to send request: device did not respond",
            id="timeout",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "data", "method"),
    [
        pytest.param(
            ZHAService.SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            SET_ATTRIBUTE_DATA,
            "write_zigbee_attribute",
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            CLUSTER_COMMAND_DATA,
            "issue_cluster_command",
            id="issue_zigbee_cluster_command",
        ),
    ],
)
async def test_cluster_service_radio_failure(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    service: str,
    data: dict,
    method: str,
    side_effect: Exception,
    message: str,
) -> None:
    """Test a radio failure in a cluster action raises a readable error."""
    await setup_zha()
    zha_device = _add_switch_device(hass, zigpy_device_mock)

    with (
        patch.object(zha_device, method, AsyncMock(side_effect=side_effect)),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE, **data}, blocking=True
        )

    assert str(err.value) == message


@pytest.mark.parametrize(
    ("data", "method"),
    [
        pytest.param({}, "permit", id="permit"),
        pytest.param(
            {"qr_code": "000D6FFFFED4163B|52797BF4A5084DAA8E1712B61741CA024051"},
            "permit_with_link_key",
            id="permit_with_link_key",
        ),
    ],
)
async def test_permit_radio_failure(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_app_controller: ControllerApplication,
    data: dict[str, Any],
    method: str,
) -> None:
    """Test a radio failure when permitting joins raises a readable error."""
    await setup_zha()
    getattr(zigpy_app_controller, method).side_effect = zigpy.exceptions.DeliveryError(
        "Failed to deliver packet", 225
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(DOMAIN, ZHAService.PERMIT, data, blocking=True)

    assert str(err.value) == "Failed to send request: Failed to deliver packet"


async def test_remove_radio_failure(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    zigpy_app_controller: ControllerApplication,
) -> None:
    """Test a radio failure when removing a device raises a readable error."""
    await setup_zha()
    _add_switch_device(hass, zigpy_device_mock)
    zigpy_app_controller.remove = AsyncMock(
        side_effect=zigpy.exceptions.DeliveryError("Failed to deliver packet", 225)
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, ZHAService.REMOVE, {"ieee": IEEE_SWITCH_DEVICE}, blocking=True
        )

    assert str(err.value) == "Failed to send request: Failed to deliver packet"


@pytest.mark.parametrize(
    "service", [ZHAService.WARNING_DEVICE_SQUAWK, ZHAService.WARNING_DEVICE_WARN]
)
async def test_warning_device_service_without_siren_raises(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    service: str,
) -> None:
    """Test the warning device actions reject a device without a siren."""
    await setup_zha()
    _add_switch_device(hass, zigpy_device_mock)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "no_warning_device"
    assert err.value.translation_placeholders == {"ieee": IEEE_SWITCH_DEVICE}


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(
            ZHAService.WARNING_DEVICE_SQUAWK, "async_squawk", id="warning_device_squawk"
        ),
        pytest.param(
            ZHAService.WARNING_DEVICE_WARN, "async_turn_on", id="warning_device_warn"
        ),
    ],
)
async def test_warning_device_service_radio_failure(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    service: str,
    method: str,
) -> None:
    """Test a radio failure in a warning device action raises a readable error."""
    await setup_zha()
    gateway = get_zha_gateway(hass)
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, security.IasWd.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_WARNING_DEVICE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee=IEEE_SWITCH_DEVICE,
    )
    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)
    siren = zha_device.get_entity(Platform.SIREN, pick_first=True)

    with (
        patch.object(
            siren,
            method,
            AsyncMock(
                side_effect=zigpy.exceptions.DeliveryError(
                    "Failed to deliver packet", 225
                )
            ),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            DOMAIN, service, {"ieee": IEEE_SWITCH_DEVICE}, blocking=True
        )

    assert str(err.value) == "Failed to send request: Failed to deliver packet"


async def test_group_command_unknown_group_raises(
    hass: HomeAssistant, setup_zha: Callable[..., Coroutine[None]]
) -> None:
    """Test the group command action rejects an unknown group."""
    await setup_zha()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
            {"group": 0x1234, "cluster_id": 6, "command": 0},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "group_not_found"
    assert err.value.translation_placeholders == {"group_id": str(0x1234)}


async def test_group_command_radio_failure(
    hass: HomeAssistant, setup_zha: Callable[..., Coroutine[None]]
) -> None:
    """Test a radio failure in the group command action raises a readable error."""
    await setup_zha()
    group = get_zha_gateway(hass).get_group(FIXTURE_GRP_ID)
    assert group is not None

    with (
        patch.object(
            group.endpoint[general.OnOff.cluster_id],
            "command",
            AsyncMock(
                side_effect=zigpy.exceptions.DeliveryError(
                    "Failed to deliver packet", 225
                )
            ),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            DOMAIN,
            ZHAService.ISSUE_ZIGBEE_GROUP_COMMAND,
            {"group": FIXTURE_GRP_ID, "cluster_id": 6, "command": 0},
            blocking=True,
        )

    assert str(err.value) == "Failed to send request: Failed to deliver packet"
