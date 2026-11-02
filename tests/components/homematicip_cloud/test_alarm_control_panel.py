"""Tests for HomematicIP Cloud alarm control panel."""

import asyncio
from typing import Any
from unittest.mock import Mock, patch

from homematicip.async_home import AsyncHome
import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.homematicip_cloud import DOMAIN
from homeassistant.components.homematicip_cloud.alarm_control_panel import (
    HomematicipAlarmControlPanelEntity,
)
from homeassistant.components.homematicip_cloud.services import SERVICE_ARM_ANYWAY
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

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


ENTITY_ID = "alarm_control_panel.hmip_alarm_control_panel"
ARMING_BLOCKED_ENTITY_ID = "binary_sensor.home_arming_blocked"


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
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def _async_arm_anyway(hass: HomeAssistant, mode: str = "away") -> None:
    """Call the arm anyway action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ARM_ANYWAY,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MODE: mode},
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
    """Test that arm anyway arms past the blocking sensors."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    assert hass.states.get(ARMING_BLOCKED_ENTITY_ID).state == STATE_ON
    home.set_security_zones_activation_with_ignore_list_async.return_value = Mock(
        success=True, json={}
    )

    await _async_arm_anyway(hass, mode)

    home.set_security_zones_activation_async.assert_awaited_with(
        expected_internal, True
    )
    home.set_security_zones_activation_with_ignore_list_async.assert_awaited_once_with(
        expected_internal,
        True,
        ignorable_device_channels=[
            {"deviceId": "3014F7110000000000000001", "channelIndex": 1}
        ],
    )
    assert hass.states.get(ARMING_BLOCKED_ENTITY_ID).state == STATE_OFF


async def test_hmip_alarm_control_panel_arm_anyway_waits_for_disarm(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a disarm sent during arm anyway runs after it, not in between."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))

    recheck_started = asyncio.Event()
    release_recheck = asyncio.Event()
    calls: list[str] = []

    async def set_zones_activation(internal: bool, external: bool) -> Mock:
        calls.append("disarm" if not external else "recheck")
        if not external:
            return Mock(success=True, json={})
        recheck_started.set()
        await release_recheck.wait()
        return _blocked("3014F7110000000000000001")

    async def set_zones_activation_with_ignore_list(
        internal: bool, external: bool, **kwargs: Any
    ) -> Mock:
        calls.append("arm")
        return Mock(success=True, json={})

    home.set_security_zones_activation_async.side_effect = set_zones_activation
    home.set_security_zones_activation_with_ignore_list_async.side_effect = (
        set_zones_activation_with_ignore_list
    )

    arm = hass.async_create_task(_async_arm_anyway(hass))
    await recheck_started.wait()
    disarm = hass.async_create_task(
        hass.services.async_call(
            "alarm_control_panel",
            "alarm_disarm",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    )
    for _ in range(10):
        await asyncio.sleep(0)
    release_recheck.set()
    await arm
    await disarm

    assert calls == ["recheck", "arm", "disarm"]


async def test_hmip_alarm_control_panel_arm_anyway_rechecks(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a device blocking since the decision stops the arming."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_with_ignore_list_async.return_value = Mock(
        success=True, json={}
    )

    # a second window opened between the refusal and the decision
    home.set_security_zones_activation_async.return_value = _blocked(
        "3014F7110000000000000001", "3014F7110000000000000005"
    )
    with pytest.raises(HomeAssistantError, match="more sensors.*Fenster, Wohnzimmer"):
        await _async_arm_anyway(hass)

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()
    assert hass.states.get(ARMING_BLOCKED_ENTITY_ID).state == STATE_ON

    # the refusal named both, so a second call arms past both
    await _async_arm_anyway(hass)

    home.set_security_zones_activation_with_ignore_list_async.assert_awaited_once()


async def test_hmip_alarm_control_panel_arm_anyway_rechecks_per_channel(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a second channel of an approved device still stops the arming."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001:1"))

    # same device, second channel, so the labels stay identical
    home.set_security_zones_activation_async.return_value = _blocked(
        "3014F7110000000000000001:1", "3014F7110000000000000001:3"
    )
    with pytest.raises(HomeAssistantError, match="more sensors"):
        await _async_arm_anyway(hass)

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()


async def test_hmip_alarm_control_panel_arm_anyway_without_refusal(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that arm anyway needs a refusal the user has seen first."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    home.set_security_zones_activation_async.return_value = _blocked(
        "3014F7110000000000000001"
    )

    with pytest.raises(HomeAssistantError, match="more sensors"):
        await _async_arm_anyway(hass)

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()


async def test_hmip_alarm_control_panel_arm_anyway_after_success(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a command going through drops the devices of an older refusal."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_async.return_value = Mock(success=True, json={})
    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_disarm",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    # the same window blocks again, but the user has not seen that refusal
    home.set_security_zones_activation_async.return_value = _blocked(
        "3014F7110000000000000001"
    )
    with pytest.raises(HomeAssistantError, match="more sensors"):
        await _async_arm_anyway(hass)

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()


async def test_hmip_alarm_control_panel_arm_anyway_no_longer_blocked(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a window closed since the decision leads to a normal arming."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_async.return_value = Mock(success=True, json={})

    await _async_arm_anyway(hass)

    home.set_security_zones_activation_with_ignore_list_async.assert_not_awaited()
    assert hass.states.get(ARMING_BLOCKED_ENTITY_ID).state == STATE_OFF


async def test_hmip_alarm_control_panel_arm_anyway_failed(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a refused arm anyway is reported."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home
    await _async_refuse_arming(hass, home, _blocked("3014F7110000000000000001"))
    home.set_security_zones_activation_with_ignore_list_async.return_value = Mock(
        success=False, json={}
    )

    with pytest.raises(HomeAssistantError, match="did not accept"):
        await _async_arm_anyway(hass)


async def test_hmip_alarm_control_panel_removal_removes_home_callback(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test removing the alarm panel removes its home update handler."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home

    def _entity_handlers() -> list[Any]:
        return [
            handler
            for handler in home._on_update
            if getattr(getattr(handler, "__self__", None), "entity_id", None)
            == entity_id
        ]

    assert len(_entity_handlers()) == 1

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert _entity_handlers() == []
    assert hass.states.get(entity_id) is None

    await _async_manipulate_security_zones(
        hass, home, internal_active=True, external_active=True
    )
    assert hass.states.get(entity_id) is None


async def test_hmip_alarm_control_panel_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test a renamed alarm panel keeps following home updates in place."""
    entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    new_entity_id = "alarm_control_panel.renamed"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    home = mock_hap.home

    with patch.object(
        HomematicipAlarmControlPanelEntity,
        "async_added_to_hass",
        autospec=True,
        side_effect=HomematicipAlarmControlPanelEntity.async_added_to_hass,
    ) as mock_added_to_hass:
        entity_registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
        await hass.async_block_till_done()

    # The entity_id is changed in place, the entity is not added again
    mock_added_to_hass.assert_not_called()
    assert hass.states.get(entity_id) is None
    assert hass.states.get(new_entity_id).state == AlarmControlPanelState.DISARMED

    await _async_manipulate_security_zones(
        hass, home, internal_active=True, external_active=True
    )
    assert hass.states.get(new_entity_id).state == AlarmControlPanelState.ARMED_AWAY
