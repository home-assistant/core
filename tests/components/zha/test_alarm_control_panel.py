"""Test ZHA alarm control panel."""

from collections.abc import Callable, Coroutine
from unittest.mock import AsyncMock, call, patch, sentinel

import pytest
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl import Cluster
from zigpy.zcl.clusters import security
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.zha.const import ATTR_IEEE
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import find_entity_id
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def alarm_control_panel_platform_only():
    """Only set up the alarm_control_panel and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.ALARM_CONTROL_PANEL,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SELECT,
        ),
    ):
        yield


@patch(
    "zigpy.zcl.clusters.security.IasAce.client_command",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_alarm_control_panel(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test ZHA alarm control panel platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [security.IasAce.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.IAS_ANCILLARY_CONTROL,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.ALARM_CONTROL_PANEL, zha_device_proxy, hass)
    cluster = zigpy_device.endpoints[1].out_clusters[security.IasAce.cluster_id]
    assert entity_id is not None

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    # arm_away from HA
    cluster.client_command.reset_mock()
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_away",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY
    assert cluster.client_command.call_count == 2
    assert cluster.client_command.await_count == 2
    assert cluster.client_command.call_args == call(
        4,
        security.IasAce.PanelStatus.Armed_Away,
        0,
        security.IasAce.AudibleNotification.Default_Sound,
        security.IasAce.AlarmStatus.No_Alarm,
    )

    # disarm from HA
    await reset_alarm_panel(hass, cluster, entity_id)

    # trip alarm from faulty code entry
    cluster.client_command.reset_mock()
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_away",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY
    cluster.client_command.reset_mock()
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_disarm",
        {ATTR_ENTITY_ID: entity_id, "code": "1111"},
        blocking=True,
    )
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_disarm",
        {ATTR_ENTITY_ID: entity_id, "code": "1111"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED
    assert cluster.client_command.call_count == 4
    assert cluster.client_command.await_count == 4
    assert cluster.client_command.call_args == call(
        4,
        security.IasAce.PanelStatus.In_Alarm,
        0,
        security.IasAce.AudibleNotification.Default_Sound,
        security.IasAce.AlarmStatus.Emergency,
    )

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    # arm_home from HA
    cluster.client_command.reset_mock()
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_home",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_HOME
    assert cluster.client_command.call_count == 2
    assert cluster.client_command.await_count == 2
    assert cluster.client_command.call_args == call(
        4,
        security.IasAce.PanelStatus.Armed_Stay,
        0,
        security.IasAce.AudibleNotification.Default_Sound,
        security.IasAce.AlarmStatus.No_Alarm,
    )

    # arm_night from HA
    cluster.client_command.reset_mock()
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_night",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_NIGHT
    assert cluster.client_command.call_count == 2
    assert cluster.client_command.await_count == 2
    assert cluster.client_command.call_args == call(
        4,
        security.IasAce.PanelStatus.Armed_Night,
        0,
        security.IasAce.AudibleNotification.Default_Sound,
        security.IasAce.AlarmStatus.No_Alarm,
    )

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    # arm from panel
    cluster.listener_event(
        "cluster_command", 1, 0, [security.IasAce.ArmMode.Arm_All_Zones, "", 0]
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    # arm day home only from panel
    cluster.listener_event(
        "cluster_command", 1, 0, [security.IasAce.ArmMode.Arm_Day_Home_Only, "", 0]
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_HOME

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    # arm night sleep only from panel
    cluster.listener_event(
        "cluster_command", 1, 0, [security.IasAce.ArmMode.Arm_Night_Sleep_Only, "", 0]
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_NIGHT

    # disarm from panel with bad code
    cluster.listener_event(
        "cluster_command", 1, 0, [security.IasAce.ArmMode.Disarm, "", 0]
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_NIGHT

    # disarm from panel with bad code for 2nd time trips alarm
    cluster.listener_event(
        "cluster_command", 1, 0, [security.IasAce.ArmMode.Disarm, "", 0]
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED

    # disarm from panel with good code
    cluster.listener_event(
        "cluster_command", 1, 0, [security.IasAce.ArmMode.Disarm, "4321", 0]
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    # panic from panel
    cluster.listener_event("cluster_command", 1, 4, [])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    # fire from panel
    cluster.listener_event("cluster_command", 1, 3, [])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    # emergency from panel
    cluster.listener_event("cluster_command", 1, 2, [])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)

    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_trigger",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED
    assert cluster.client_command.call_count == 1
    assert cluster.client_command.await_count == 1
    assert cluster.client_command.call_args == call(
        4,
        security.IasAce.PanelStatus.In_Alarm,
        0,
        security.IasAce.AudibleNotification.Default_Sound,
        security.IasAce.AlarmStatus.Emergency_Panic,
    )

    # reset the panel
    await reset_alarm_panel(hass, cluster, entity_id)
    cluster.client_command.reset_mock()


async def reset_alarm_panel(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Reset the state of the alarm panel."""
    cluster.client_command.reset_mock()
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_disarm",
        {ATTR_ENTITY_ID: entity_id, "code": "4321"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED
    assert cluster.client_command.call_count == 2
    assert cluster.client_command.await_count == 2
    assert cluster.client_command.call_args == call(
        4,
        security.IasAce.PanelStatus.Panel_Disarmed,
        0,
        security.IasAce.AudibleNotification.Default_Sound,
        security.IasAce.AlarmStatus.No_Alarm,
    )
    cluster.client_command.reset_mock()


@patch(
    "zigpy.zcl.clusters.security.IasAce.client_command",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_set_entry_delay_service(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test set_entry_delay service."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [security.IasAce.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.IAS_ANCILLARY_CONTROL,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device = gateway.get_device(zigpy_device.ieee)

    # Get the IAS ACE cluster handler
    ias_ace_ch = None
    for endpoint in zha_device.endpoints.values():
        if hasattr(endpoint, "client_cluster_handlers_by_name"):
            ias_ace_ch = endpoint.client_cluster_handlers_by_name.get("ias_ace")
            if ias_ace_ch:
                break
    assert ias_ace_ch is not None, "IAS ACE cluster handler not found"

    # Test setting entry delay successfully
    with patch.object(ias_ace_ch, "start_entry_delay") as mock_start_entry_delay:
        await hass.services.async_call(
            "zha",
            "set_entry_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 45,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_start_entry_delay.assert_called_once_with(45)

    # Test with different duration
    with patch.object(ias_ace_ch, "start_entry_delay") as mock_start_entry_delay:
        await hass.services.async_call(
            "zha",
            "set_entry_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 120,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_start_entry_delay.assert_called_once_with(120)

    # Test error when device doesn't exist
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            "zha",
            "set_entry_delay",
            {
                ATTR_IEEE: "00:11:22:33:44:55:66:77",
                "duration": 30,
            },
            blocking=True,
        )
    await hass.async_block_till_done()
    assert "not found" in str(exc_info.value).lower()


@patch(
    "zigpy.zcl.clusters.security.IasAce.client_command",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_set_exit_delay_service(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test set_exit_delay service."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [],
                SIG_EP_OUTPUT: [security.IasAce.cluster_id],
                SIG_EP_TYPE: zha.DeviceType.IAS_ANCILLARY_CONTROL,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device = gateway.get_device(zigpy_device.ieee)

    # Get the IAS ACE cluster handler
    ias_ace_ch = None
    for endpoint in zha_device.endpoints.values():
        if hasattr(endpoint, "client_cluster_handlers_by_name"):
            ias_ace_ch = endpoint.client_cluster_handlers_by_name.get("ias_ace")
            if ias_ace_ch:
                break
    assert ias_ace_ch is not None, "IAS ACE cluster handler not found"

    # Test exit delay for "away" mode
    with (
        patch.object(ias_ace_ch, "start_exit_delay") as mock_start_exit_delay,
        patch.object(
            ias_ace_ch, "arm_response", new_callable=AsyncMock
        ) as mock_arm_response,
    ):
        await hass.services.async_call(
            "zha",
            "set_exit_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 60,
                "arm_mode": "away",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_start_exit_delay.assert_called_once_with(
            60, security.IasAce.PanelStatus.Armed_Away
        )
        mock_arm_response.assert_called_once_with(
            security.IasAce.ArmNotification.All_Zones_Armed
        )

    # Test exit delay for "home" mode
    with (
        patch.object(ias_ace_ch, "start_exit_delay") as mock_start_exit_delay,
        patch.object(
            ias_ace_ch, "arm_response", new_callable=AsyncMock
        ) as mock_arm_response,
    ):
        await hass.services.async_call(
            "zha",
            "set_exit_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 90,
                "arm_mode": "home",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_start_exit_delay.assert_called_once_with(
            90, security.IasAce.PanelStatus.Armed_Stay
        )
        mock_arm_response.assert_called_once_with(
            security.IasAce.ArmNotification.Only_Day_Home_Zones_Armed
        )

    # Test exit delay for "night" mode
    with (
        patch.object(ias_ace_ch, "start_exit_delay") as mock_start_exit_delay,
        patch.object(
            ias_ace_ch, "arm_response", new_callable=AsyncMock
        ) as mock_arm_response,
    ):
        await hass.services.async_call(
            "zha",
            "set_exit_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 30,
                "arm_mode": "night",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_start_exit_delay.assert_called_once_with(
            30, security.IasAce.PanelStatus.Armed_Night
        )
        mock_arm_response.assert_called_once_with(
            security.IasAce.ArmNotification.Only_Night_Sleep_Zones_Armed
        )

    # Test error when device doesn't exist
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            "zha",
            "set_exit_delay",
            {
                ATTR_IEEE: "00:11:22:33:44:55:66:77",
                "duration": 30,
                "arm_mode": "away",
            },
            blocking=True,
        )
    await hass.async_block_till_done()
    assert "not found" in str(exc_info.value).lower()


@patch(
    "zigpy.zcl.clusters.security.IasAce.client_command",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_set_entry_delay_service_no_ias_ace(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test set_entry_delay service with device that doesn't have IAS ACE cluster."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    # Create device without IAS ACE cluster
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [0],
                SIG_EP_OUTPUT: [0],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Test error when device doesn't have IAS ACE cluster
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "zha",
            "set_entry_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 30,
            },
            blocking=True,
        )


@patch(
    "zigpy.zcl.clusters.security.IasAce.client_command",
    new=AsyncMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
async def test_set_exit_delay_service_no_ias_ace(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test set_exit_delay service with device that doesn't have IAS ACE cluster."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    # Create device without IAS ACE cluster
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [0],
                SIG_EP_OUTPUT: [0],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Test error when device doesn't have IAS ACE cluster
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "zha",
            "set_exit_delay",
            {
                ATTR_IEEE: str(zigpy_device.ieee),
                "duration": 30,
                "arm_mode": "away",
            },
            blocking=True,
        )
