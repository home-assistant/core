"""Tests for HomematicIP Cloud alarm control panel."""

from unittest.mock import Mock

from homematicip.async_home import AsyncHome
import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.homematicip_cloud import DOMAIN
from homeassistant.components.homematicip_cloud.alarm_control_panel import (
    SERVICE_ARM_ANYWAY,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .helper import HomeFactory, get_and_check_entity_basics


async def _async_manipulate_security_zones(
    hass: HomeAssistant,
    home: AsyncHome,
    internal_active: bool = False,
    external_active: bool = False,
    alarm_triggered: bool = False,
) -> None:
    """Set new values on hmip security zones."""
    json = home._rawJSONData
    json["functionalHomes"]["SECURITY_AND_ALARM"]["alarmActive"] = alarm_triggered
    external_zone_id = json["functionalHomes"]["SECURITY_AND_ALARM"]["securityZones"][
        "EXTERNAL"
    ]
    internal_zone_id = json["functionalHomes"]["SECURITY_AND_ALARM"]["securityZones"][
        "INTERNAL"
    ]
    external_zone = home.search_group_by_id(external_zone_id)
    external_zone.active = external_active
    internal_zone = home.search_group_by_id(internal_zone_id)
    internal_zone.active = internal_active

    home.update_home_only(json)
    home.fire_update_event(json)
    await hass.async_block_till_done()


async def test_hmip_alarm_control_panel(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipAlarmControlPanel."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    entity_name = "HmIP Alarm Control Panel"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == "disarmed"
    assert not hmip_device

    home = mock_hap.home
    # the mocked connection answers every call with a tuple, not a RestResult
    home.set_security_zones_activation_async.return_value = Mock(success=True, json={})

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=True
    )
    home.set_security_zones_activation_async.assert_awaited_with(True, True)
    await _async_manipulate_security_zones(
        hass, home, internal_active=True, external_active=True
    )
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_AWAY

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_home", {"entity_id": entity_id}, blocking=True
    )
    home.set_security_zones_activation_async.assert_awaited_with(False, True)
    await _async_manipulate_security_zones(hass, home, external_active=True)
    assert hass.states.get(entity_id).state == AlarmControlPanelState.ARMED_HOME

    await hass.services.async_call(
        "alarm_control_panel", "alarm_disarm", {"entity_id": entity_id}, blocking=True
    )
    home.set_security_zones_activation_async.assert_awaited_with(False, False)
    await _async_manipulate_security_zones(hass, home)
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=True
    )
    home.set_security_zones_activation_async.assert_awaited_with(True, True)
    await _async_manipulate_security_zones(
        hass, home, internal_active=True, external_active=True, alarm_triggered=True
    )
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED

    await hass.services.async_call(
        "alarm_control_panel", "alarm_arm_home", {"entity_id": entity_id}, blocking=True
    )
    home.set_security_zones_activation_async.assert_awaited_with(False, True)
    await _async_manipulate_security_zones(
        hass, home, external_active=True, alarm_triggered=True
    )
    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED


async def test_hmip_alarm_control_panel_activation_blocked(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a refused activation names the blocking devices."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    home.set_security_zones_activation_async.return_value = Mock(
        success=False,
        json={
            "channelActivationProblems": {
                "3014F7110000000000000001:1": ["WINDOW_OPEN"],
                "3014F7110000000000000005:1": ["WINDOW_OPEN"],
            }
        },
    )

    with pytest.raises(HomeAssistantError, match="Fenster, Wohnzimmer"):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_away",
            {"entity_id": entity_id},
            blocking=True,
        )

    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


async def test_hmip_alarm_control_panel_activation_failed(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test a refusal that does not name any device."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    home.set_security_zones_activation_async.return_value = Mock(success=False, json={})

    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_home",
            {"entity_id": entity_id},
            blocking=True,
        )


def _blocked(*channels: str) -> Mock:
    """Build the reply of a refused activation.

    Entries are device ids, optionally with a channel index appended.
    """
    return Mock(
        success=False,
        json={
            "channelActivationProblems": {
                channel if ":" in channel else f"{channel}:1": ["WINDOW_OPEN"]
                for channel in channels
            }
        },
    )


async def _async_refuse_arming(hass: HomeAssistant, home: Mock, blocked: Mock) -> None:
    """Run the refused arming attempt the user bases the decision on."""
    home.set_security_zones_activation_async.return_value = blocked
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_away",
            {"entity_id": "alarm_control_panel.hmip_alarm_control_panel"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("mode", "expected_internal"),
    [("away", True), ("home", False)],
)
async def test_hmip_alarm_control_panel_arm_anyway(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    mode: str,
    expected_internal: bool,
) -> None:
    """Test that arm_anyway arms past the blocking sensors."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_with_ignore_list_async.return_value = Mock(
        success=True, json={}
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ARM_ANYWAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_MODE: mode},
        blocking=True,
    )

    home.set_security_zones_activation_with_ignore_list_async.assert_awaited_once_with(
        expected_internal, True
    )


async def test_hmip_alarm_control_panel_arm_anyway_rechecks(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a device blocking since the decision stops the arming."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))

    # a second window opened between the refusal and the decision
    home.set_security_zones_activation_async.return_value = _blocked(
        "3014F7110000000000000001", "3014F7110000000000000005"
    )

    with pytest.raises(HomeAssistantError, match="Fenster, Wohnzimmer"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ARM_ANYWAY,
            {ATTR_ENTITY_ID: entity_id, ATTR_MODE: "away"},
            blocking=True,
        )

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()


async def test_hmip_alarm_control_panel_arm_anyway_rechecks_per_channel(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a second channel of an approved device still stops the arming."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001:1"))

    # same device, second channel, so the labels stay identical
    home.set_security_zones_activation_async.return_value = _blocked(
        "3014F7110000000000000001:1", "3014F7110000000000000001:3"
    )

    with pytest.raises(HomeAssistantError, match="Fenster"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ARM_ANYWAY,
            {ATTR_ENTITY_ID: entity_id, ATTR_MODE: "away"},
            blocking=True,
        )

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()


async def test_hmip_alarm_control_panel_arm_anyway_no_longer_blocked(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a window closed since the decision leads to a normal arming."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_async.return_value = Mock(success=True, json={})

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ARM_ANYWAY,
        {ATTR_ENTITY_ID: entity_id, ATTR_MODE: "away"},
        blocking=True,
    )

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()


async def test_hmip_alarm_control_panel_arm_anyway_failed(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a refused arm_anyway is reported."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_with_ignore_list_async.return_value = Mock(
        success=False, json={}
    )

    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ARM_ANYWAY,
            {ATTR_ENTITY_ID: entity_id, ATTR_MODE: "away"},
            blocking=True,
        )
