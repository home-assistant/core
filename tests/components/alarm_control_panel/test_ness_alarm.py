"""Tests for the ness_alarm alarm control panel component."""

from enum import Enum

import pytest
from asynctest import patch, Mock

from homeassistant.components.alarm_control_panel.ness_alarm import (
    NessAlarmPanel)
from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMING,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_TRIGGERED, STATE_ALARM_PENDING)
from tests.common import MockDependency


async def test_handle_arming_state_change(hass, mock_arming_state):
    """Test arming state change handing."""
    states = [
        (MockArmingState.UNKNOWN, None),
        (MockArmingState.DISARMED, STATE_ALARM_DISARMED),
        (MockArmingState.ARMING, STATE_ALARM_ARMING),
        (MockArmingState.EXIT_DELAY, STATE_ALARM_ARMING),
        (MockArmingState.ARMED, STATE_ALARM_ARMED_AWAY),
        (MockArmingState.ENTRY_DELAY, STATE_ALARM_PENDING),
        (MockArmingState.TRIGGERED, STATE_ALARM_TRIGGERED),
    ]

    for arming_state, expected_state in states:
        alarm_panel = NessAlarmPanel(client=Mock(), name='Alarm Panel')
        alarm_panel.hass = hass
        mock_update_ha_state = Mock()
        alarm_panel.async_schedule_update_ha_state = mock_update_ha_state

        assert alarm_panel.state is None
        alarm_panel._handle_arming_state_change(arming_state)
        assert alarm_panel.state == expected_state
        assert mock_update_ha_state.call_count == 1


async def test_availability(hass, mock_arming_state):
    """Test entity is unavailable until a zone update is handled."""
    alarm_panel = NessAlarmPanel(client=Mock(), name='Alarm Panel')
    alarm_panel.hass = hass
    mock_update_ha_state = Mock()
    alarm_panel.async_schedule_update_ha_state = mock_update_ha_state

    assert alarm_panel.available is False
    alarm_panel._handle_arming_state_change(MockArmingState.ARMED)
    assert alarm_panel.available is True


@pytest.fixture
def mock_arming_state():
    """Mock nessclient ArmingState enum."""
    with MockDependency('nessclient'), \
         patch('nessclient.ArmingState', new=MockArmingState) as mock:
        yield mock


class MockArmingState(Enum):
    """Mock nessclient.ArmingState enum."""

    UNKNOWN = 'UNKNOWN'
    DISARMED = 'DISARMED'
    ARMING = 'ARMING'
    EXIT_DELAY = 'EXIT_DELAY'
    ARMED = 'ARMED'
    ENTRY_DELAY = 'ENTRY_DELAY'
    TRIGGERED = 'TRIGGERED'
