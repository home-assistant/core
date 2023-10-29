"""Tests for the Freebox sensors."""
from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL,
    AlarmControlPanelEntityFeature,
)
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.const import (
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from .common import setup_platform
from .const import DATA_HOME_ALARM_GET_VALUES

from tests.common import async_fire_time_changed, async_mock_service


async def test_panel(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test home binary sensors."""
    await setup_platform(hass, ALARM_CONTROL_PANEL)

    # Initial state
    assert hass.states.get("alarm_control_panel.systeme_d_alarme").state == "unknown"
    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").attributes[
            "supported_features"
        ]
        == AlarmControlPanelEntityFeature.ARM_AWAY
    )

    # Now simulate a changed status
    data_get_home_endpoint_value = deepcopy(DATA_HOME_ALARM_GET_VALUES)
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state == "armed_night"
    )
    # Fake that the entity is triggered.
    hass.states.async_set("alarm_control_panel.systeme_d_alarme", STATE_ALARM_DISARMED)
    assert hass.states.get("alarm_control_panel.systeme_d_alarme").state == "disarmed"


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Alarm control panel states."""
    hass.states.async_set(
        "alarm_control_panel.entity_armed_away", STATE_ALARM_ARMED_AWAY, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_custom_bypass",
        STATE_ALARM_ARMED_CUSTOM_BYPASS,
        {},
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_home", STATE_ALARM_ARMED_HOME, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_night", STATE_ALARM_ARMED_NIGHT, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_armed_vacation", STATE_ALARM_ARMED_VACATION, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_disarmed", STATE_ALARM_DISARMED, {}
    )
    hass.states.async_set(
        "alarm_control_panel.entity_triggered", STATE_ALARM_TRIGGERED, {}
    )

    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_ARM_AWAY)
    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_ARM_CUSTOM_BYPASS)
    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_ARM_HOME)
    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_ARM_NIGHT)
    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_ARM_VACATION)
    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_DISARM)
    async_mock_service(hass, "alarm_control_panel", SERVICE_ALARM_TRIGGER)

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("alarm_control_panel.entity_armed_away", STATE_ALARM_ARMED_AWAY),
            State(
                "alarm_control_panel.entity_armed_custom_bypass",
                STATE_ALARM_ARMED_CUSTOM_BYPASS,
            ),
            State("alarm_control_panel.entity_armed_home", STATE_ALARM_ARMED_HOME),
            State("alarm_control_panel.entity_armed_night", STATE_ALARM_ARMED_NIGHT),
            State(
                "alarm_control_panel.entity_armed_vacation", STATE_ALARM_ARMED_VACATION
            ),
            State("alarm_control_panel.entity_disarmed", STATE_ALARM_DISARMED),
            State("alarm_control_panel.entity_triggered", STATE_ALARM_TRIGGERED),
        ],
    )
