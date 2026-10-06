"""Tests for the bosch_shc alarm control panel platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import SHCIntrusionSystem
import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    Platform,
)
from homeassistant.core import HomeAssistant

from .conftest import intrusion_system_device, setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "alarm_control_panel.alarm_system"
ArmingState = SHCIntrusionSystem.ArmingState
AlarmState = SHCIntrusionSystem.AlarmState
Profile = SHCIntrusionSystem.Profile


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the alarm control panel platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        yield


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, AlarmControlPanelState.DISARMED),
        (
            {"arming_state": ArmingState.SYSTEM_ARMING},
            AlarmControlPanelState.ARMING,
        ),
        (
            {"arming_state": ArmingState.SYSTEM_ARMED},
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            {
                "arming_state": ArmingState.SYSTEM_ARMED,
                "profile": Profile.PARTIAL_PROTECTION,
            },
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            {
                "arming_state": ArmingState.SYSTEM_ARMED,
                "profile": Profile.CUSTOM_PROTECTION,
            },
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (
            {
                "arming_state": ArmingState.SYSTEM_ARMED,
                "profile": Profile.UNKNOWN,
            },
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (
            {"alarm_state": AlarmState.PRE_ALARM},
            AlarmControlPanelState.PENDING,
        ),
        (
            {"alarm_state": AlarmState.ALARM_ON},
            AlarmControlPanelState.TRIGGERED,
        ),
        (
            {"alarm_state": AlarmState.ALARM_MUTED},
            AlarmControlPanelState.TRIGGERED,
        ),
    ],
)
async def test_alarm_state(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    kwargs: dict,
    expected: AlarmControlPanelState,
) -> None:
    """The SHC arming, alarm and profile state map to the panel state."""
    mock_session.intrusion_system = intrusion_system_device(**kwargs)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_ALARM_DISARM, "disarm"),
        (SERVICE_ALARM_ARM_AWAY, "arm_full_protection"),
        (SERVICE_ALARM_ARM_HOME, "arm_partial_protection"),
        (SERVICE_ALARM_ARM_CUSTOM_BYPASS, "arm_individual_protection"),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Each alarm service calls the matching SHC command."""
    device = intrusion_system_device()
    mock_session.intrusion_system = device
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(device, method).assert_called_once_with()


async def test_unavailable(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The panel is unavailable when the system reports unavailable."""
    device = intrusion_system_device()
    device.system_availability = False
    mock_session.intrusion_system = device
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == "unavailable"
