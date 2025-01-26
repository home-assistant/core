"""Test ZHA lock."""

from unittest.mock import patch

import pytest
from zigpy.profiles import zha
from zigpy.zcl import Cluster
from zigpy.zcl.clusters import closures, general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Only set up the lock and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.LOCK,
            Platform.SENSOR,
        ),
    ):
        yield


async def test_lock(hass: HomeAssistant, setup_zha, zigpy_device_mock) -> None:
    """Test ZHA lock platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [closures.DoorLock.cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.DOOR_LOCK,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.LOCK, zha_device_proxy, hass)
    cluster = zigpy_device.endpoints[1].door_lock
    assert entity_id is not None

    assert hass.states.get(entity_id).state == LockState.UNLOCKED

    # set state to locked
    await send_attributes_report(
        hass,
        cluster,
        {closures.DoorLock.AttributeDefs.lock_state.id: closures.LockState.Locked},
    )
    assert hass.states.get(entity_id).state == LockState.LOCKED

    # set state to unlocked
    await send_attributes_report(
        hass,
        cluster,
        {closures.DoorLock.AttributeDefs.lock_state.id: closures.LockState.Unlocked},
    )
    assert hass.states.get(entity_id).state == LockState.UNLOCKED

    # lock from HA
    await async_lock(hass, cluster, entity_id)

    # unlock from HA
    await async_unlock(hass, cluster, entity_id)

    # set user code
    await async_set_user_code(hass, cluster, entity_id)

    # clear user code
    await async_clear_user_code(hass, cluster, entity_id)

    # enable user code
    await async_enable_user_code(hass, cluster, entity_id)

    # disable user code
    await async_disable_user_code(hass, cluster, entity_id)


async def async_lock(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test lock functionality from hass."""
    with patch("zigpy.zcl.Cluster.request", return_value=[zcl_f.Status.SUCCESS]):
        # lock via UI
        await hass.services.async_call(
            LOCK_DOMAIN, "lock", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert (
            cluster.request.call_args[0][1]
            == closures.DoorLock.ServerCommandDefs.lock_door.id
        )


async def async_unlock(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test lock functionality from hass."""
    with patch("zigpy.zcl.Cluster.request", return_value=[zcl_f.Status.SUCCESS]):
        # lock via UI
        await hass.services.async_call(
            LOCK_DOMAIN, "unlock", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert (
            cluster.request.call_args[0][1]
            == closures.DoorLock.ServerCommandDefs.unlock_door.id
        )


async def async_set_user_code(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test set lock code functionality from hass."""
    with patch("zigpy.zcl.Cluster.request", return_value=[zcl_f.Status.SUCCESS]):
        # set lock code via service call
        await hass.services.async_call(
            "zha",
            "set_lock_user_code",
            {"entity_id": entity_id, "code_slot": 3, "user_code": "13246579"},
            blocking=True,
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert (
            cluster.request.call_args[0][1]
            == closures.DoorLock.ServerCommandDefs.set_pin_code.id
        )
        assert cluster.request.call_args[0][3] == 2  # user slot 3 => internal slot 2
        assert cluster.request.call_args[0][4] == closures.DoorLock.UserStatus.Enabled
        assert (
            cluster.request.call_args[0][5] == closures.DoorLock.UserType.Unrestricted
        )
        assert cluster.request.call_args[0][6] == "13246579"


async def async_clear_user_code(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test clear lock code functionality from hass."""
    with patch("zigpy.zcl.Cluster.request", return_value=[zcl_f.Status.SUCCESS]):
        # set lock code via service call
        await hass.services.async_call(
            "zha",
            "clear_lock_user_code",
            {
                "entity_id": entity_id,
                "code_slot": 3,
            },
            blocking=True,
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert (
            cluster.request.call_args[0][1]
            == closures.DoorLock.ServerCommandDefs.clear_pin_code.id
        )
        assert cluster.request.call_args[0][3] == 2  # user slot 3 => internal slot 2


async def async_enable_user_code(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test enable lock code functionality from hass."""
    with patch("zigpy.zcl.Cluster.request", return_value=[zcl_f.Status.SUCCESS]):
        # set lock code via service call
        await hass.services.async_call(
            "zha",
            "enable_lock_user_code",
            {
                "entity_id": entity_id,
                "code_slot": 3,
            },
            blocking=True,
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert (
            cluster.request.call_args[0][1]
            == closures.DoorLock.ServerCommandDefs.set_user_status.id
        )
        assert cluster.request.call_args[0][3] == 2  # user slot 3 => internal slot 2
        assert cluster.request.call_args[0][4] == closures.DoorLock.UserStatus.Enabled


async def async_disable_user_code(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test disable lock code functionality from hass."""
    with patch("zigpy.zcl.Cluster.request", return_value=[zcl_f.Status.SUCCESS]):
        # set lock code via service call
        await hass.services.async_call(
            "zha",
            "disable_lock_user_code",
            {
                "entity_id": entity_id,
                "code_slot": 3,
            },
            blocking=True,
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert (
            cluster.request.call_args[0][1]
            == closures.DoorLock.ServerCommandDefs.set_user_status.id
        )
        assert cluster.request.call_args[0][3] == 2  # user slot 3 => internal slot 2
        assert cluster.request.call_args[0][4] == closures.DoorLock.UserStatus.Disabled
