"""Test the UniFi Protect alarm control panel platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import NVR, NvrArmMode, NvrArmModeStatus, PublicBootstrap
from uiprotect.exceptions import GlobalAlarmManagerError
from uiprotect.websocket import WebsocketState

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_DISARM,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .utils import MockUFPFixture, assert_entity_counts, init_entry

ALARM_ENTITY_ID = "alarm_control_panel.unifiprotect_alarm_manager"


def _make_arm_mode(status: NvrArmModeStatus) -> Mock:
    """Create a NvrArmMode object for testing."""
    arm_mode = Mock(spec=NvrArmMode)
    arm_mode.status = status
    return arm_mode


def _make_public_bootstrap(arm_mode: Mock | None) -> Mock:
    """Create a PublicBootstrap with the given arm_mode."""
    pb = Mock(spec=PublicBootstrap)
    pb.arm_mode = arm_mode
    pb.arm_profiles = {}
    pb.sirens = {}
    return pb


async def test_alarm_panel_not_created_without_public_bootstrap(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Alarm panel entity is NOT created when has_public_bootstrap is False."""
    ufp.api.has_public_bootstrap = False

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 0, 0)


async def test_alarm_panel_created_with_public_bootstrap(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """Alarm panel entity IS created when has_public_bootstrap is True."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 1, 1)

    entity = entity_registry.async_get(ALARM_ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == f"{nvr.mac}_alarm"

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


@pytest.mark.parametrize(
    ("nvr_status", "expected_state"),
    [
        (NvrArmModeStatus.DISABLED, AlarmControlPanelState.DISARMED),
        (NvrArmModeStatus.UNKNOWN, AlarmControlPanelState.DISARMED),
        (NvrArmModeStatus.ARMING, AlarmControlPanelState.ARMING),
        (NvrArmModeStatus.ARMED, AlarmControlPanelState.ARMED_AWAY),
        (NvrArmModeStatus.BREACH, AlarmControlPanelState.TRIGGERED),
    ],
)
async def test_alarm_panel_state_mapping(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr_status: NvrArmModeStatus,
    expected_state: AlarmControlPanelState,
) -> None:
    """Test that NvrArmModeStatus maps to correct AlarmControlPanelState."""
    arm_mode = _make_arm_mode(nvr_status)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_alarm_panel_not_created_without_arm_mode(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Alarm panel entity is NOT created on old firmware (arm_mode is None)."""
    pb = _make_public_bootstrap(arm_mode=None)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.ALARM_CONTROL_PANEL, 0, 0)


async def test_alarm_panel_disarm(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that disarm service calls disable_arm_alarm_public."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.disable_arm_alarm_public = AsyncMock()

    await init_entry(hass, ufp, [])

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
        blocking=True,
    )

    ufp.api.disable_arm_alarm_public.assert_called_once()


async def test_alarm_panel_arm_away(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that arm_away service calls enable_arm_alarm_public."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.enable_arm_alarm_public = AsyncMock()

    await init_entry(hass, ufp, [])

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
        blocking=True,
    )

    ufp.api.enable_arm_alarm_public.assert_called_once()


async def test_alarm_panel_disarm_global_manager_error(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that GlobalAlarmManagerError on disarm raises HomeAssistantError."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.disable_arm_alarm_public = AsyncMock(side_effect=GlobalAlarmManagerError())

    await init_entry(hass, ufp, [])

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_DISARM,
            {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "global_alarm_manager"


async def test_alarm_panel_arm_away_global_manager_error(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Test that GlobalAlarmManagerError on arm raises HomeAssistantError."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb
    ufp.api.enable_arm_alarm_public = AsyncMock(side_effect=GlobalAlarmManagerError())

    await init_entry(hass, ufp, [])

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: ALARM_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "global_alarm_manager"


async def test_alarm_panel_state_update_via_ws(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """Test that public devices WS update triggers state refresh."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.DISABLED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED

    # Simulate arm state change via the public devices websocket
    armed_arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb.arm_mode = armed_arm_mode

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = nvr
    mock_msg.new_obj = nvr
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY


async def test_alarm_panel_unavailable_when_arm_mode_disappears(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    nvr: NVR,
) -> None:
    """Entity becomes unavailable when arm_mode disappears after a WS update."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    # Simulate firmware downgrade / global mode switch: arm_mode becomes None
    pb.arm_mode = None

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = nvr
    mock_msg.new_obj = nvr
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_alarm_panel_unavailable_on_ws_disconnect(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Entity becomes unavailable when the private WebSocket disconnects."""
    arm_mode = _make_arm_mode(NvrArmModeStatus.ARMED)
    pb = _make_public_bootstrap(arm_mode)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb

    await init_entry(hass, ufp, [])

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    ufp.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    ufp.ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.ARMED_AWAY
