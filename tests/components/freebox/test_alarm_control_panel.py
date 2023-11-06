"""Tests for the Freebox alarms."""
from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntityFeature,
)
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant

from .common import setup_platform
from .const import DATA_HOME_ALARM_GET_VALUE

from tests.common import async_fire_time_changed


async def test_alarm_changed_from_external(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test Freebox Home alarm which state depends on external changes."""
    data_get_home_endpoint_value = deepcopy(DATA_HOME_ALARM_GET_VALUE)
    data_get_home_endpoint_value["value"] = "alarm1_arming"
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value
    await setup_platform(hass, ALARM_CONTROL_PANEL_DOMAIN)

    # Attributes
    assert hass.states.get("alarm_control_panel.systeme_d_alarme").attributes[
        "supported_features"
    ] == (
        AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.TRIGGER
    )

    # Initial state
    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state
        == STATE_ALARM_ARMING
    )

    # Now simulate a changed status
    data_get_home_endpoint_value = deepcopy(DATA_HOME_ALARM_GET_VALUE)
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state
        == STATE_ALARM_ARMED_AWAY
    )


async def test_alarm_changed_from_hass(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox Home alarm which state depends on HA."""
    data_get_home_endpoint_value = deepcopy(DATA_HOME_ALARM_GET_VALUE)
    data_get_home_endpoint_value["value"] = "alarm1_armed"
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value
    await setup_platform(hass, ALARM_CONTROL_PANEL_DOMAIN)

    # Attributes
    assert hass.states.get("alarm_control_panel.systeme_d_alarme").attributes[
        "supported_features"
    ] == (
        AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.TRIGGER
    )

    # Initial state: arm_away
    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state
        == STATE_ALARM_ARMED_AWAY
    )

    # Now call for a change -> disarmed
    data_get_home_endpoint_value["value"] = None
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value
    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: ["alarm_control_panel.systeme_d_alarme"]},
        blocking=True,
    )

    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state
        == STATE_ALARM_DISARMED
    )

    # Now call for a change -> arm_away
    data_get_home_endpoint_value["value"] = "alarm1_arming"
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value
    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ["alarm_control_panel.systeme_d_alarme"]},
        blocking=True,
    )

    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state
        == STATE_ALARM_ARMING
    )

    # Now call for a change -> trigger
    data_get_home_endpoint_value["value"] = "alarm1_alert_timer"
    router().home.get_home_endpoint_value.return_value = data_get_home_endpoint_value
    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_TRIGGER,
        {ATTR_ENTITY_ID: ["alarm_control_panel.systeme_d_alarme"]},
        blocking=True,
    )

    assert (
        hass.states.get("alarm_control_panel.systeme_d_alarme").state
        == STATE_ALARM_TRIGGERED
    )
