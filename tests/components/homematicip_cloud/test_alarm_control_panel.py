"""Tests for HomematicIP Cloud alarm control panel."""
from homematicip.base.enums import WindowState
from homematicip.group import SecurityZoneGroup

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.setup import async_setup_component

from .helper import get_and_check_entity_basics


def _get_security_zones(groups):  # pylint: disable=W0221
    """Get the security zones."""
    for group in groups:
        if isinstance(group, SecurityZoneGroup):
            if group.label == "EXTERNAL":
                external = group
            elif group.label == "INTERNAL":
                internal = group
    return internal, external


async def _async_manipulate_security_zones(
    hass, home, internal_active, external_active, window_state
):
    """Set new values on hmip security zones."""
    internal_zone, external_zone = _get_security_zones(home.groups)
    external_zone.active = external_active
    external_zone.windowState = window_state
    internal_zone.active = internal_active

    # Just one call to a security zone is required to refresh the ACP.
    internal_zone.fire_update_event()

    await hass.async_block_till_done()


async def test_manually_configured_platform(hass):
    """Test that we do not set up an access point."""
    assert (
        await async_setup_component(
            hass,
            ALARM_CONTROL_PANEL_DOMAIN,
            {ALARM_CONTROL_PANEL_DOMAIN: {"platform": HMIPC_DOMAIN}},
        )
        is True
    )
    assert not hass.data.get(HMIPC_DOMAIN)


async def test_hmip_alarm_control_panel(hass, default_mock_hap):
    """Test HomematicipAlarmControlPanel."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    entity_name = "HmIP Alarm Control Panel"
    device_model = None

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "disarmed"
    assert not hmip_device

    home = default_mock_hap.home
    service_call_counter = len(home.mock_calls)

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=True
    )
    assert len(home.mock_calls) == service_call_counter + 1
    assert home.mock_calls[-1][0] == "set_security_zones_activation"
    assert home.mock_calls[-1][1] == (True, True)
    await _async_manipulate_security_zones(
        hass,
        home,
        internal_active=True,
        external_active=True,
        window_state=WindowState.CLOSED,
    )
    assert hass.states.get(entity_id).state is STATE_ALARM_ARMED_AWAY

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_home", {"entity_id": entity_id}, blocking=True
    )
    assert len(home.mock_calls) == service_call_counter + 3
    assert home.mock_calls[-1][0] == "set_security_zones_activation"
    assert home.mock_calls[-1][1] == (False, True)
    await _async_manipulate_security_zones(
        hass,
        home,
        internal_active=False,
        external_active=True,
        window_state=WindowState.CLOSED,
    )
    assert hass.states.get(entity_id).state is STATE_ALARM_ARMED_HOME

    await hass.services.async_call(
        "alarm_control_panel", "alarm_disarm", {"entity_id": entity_id}, blocking=True
    )
    assert len(home.mock_calls) == service_call_counter + 5
    assert home.mock_calls[-1][0] == "set_security_zones_activation"
    assert home.mock_calls[-1][1] == (False, False)
    await _async_manipulate_security_zones(
        hass,
        home,
        internal_active=False,
        external_active=False,
        window_state=WindowState.CLOSED,
    )
    assert hass.states.get(entity_id).state is STATE_ALARM_DISARMED

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=True
    )
    assert len(home.mock_calls) == service_call_counter + 7
    assert home.mock_calls[-1][0] == "set_security_zones_activation"
    assert home.mock_calls[-1][1] == (True, True)
    await _async_manipulate_security_zones(
        hass,
        home,
        internal_active=True,
        external_active=True,
        window_state=WindowState.OPEN,
    )
    assert hass.states.get(entity_id).state is STATE_ALARM_TRIGGERED

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_home", {"entity_id": entity_id}, blocking=True
    )
    assert len(home.mock_calls) == service_call_counter + 9
    assert home.mock_calls[-1][0] == "set_security_zones_activation"
    assert home.mock_calls[-1][1] == (False, True)
    await _async_manipulate_security_zones(
        hass,
        home,
        internal_active=False,
        external_active=True,
        window_state=WindowState.OPEN,
    )
    assert hass.states.get(entity_id).state is STATE_ALARM_TRIGGERED
