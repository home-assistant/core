"""Tests for the Elk-M1 alarm control panel platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

from elkm1_lib.const import AlarmState, ArmedStatus, ArmLevel, ArmUpState
import pytest

from homeassistant.components.alarm_control_panel import (
    ATTR_CHANGED_BY,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.components.elkm1 import alarm_control_panel
from homeassistant.components.elkm1.const import (
    ATTR_CHANGED_BY_ID,
    ATTR_CHANGED_BY_KEYPAD,
    ATTR_CHANGED_BY_TIME,
    DOMAIN,
)
from homeassistant.components.elkm1.models import ELKM1Data
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_VACATION,
    Platform,
)
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry

_ENTITY_ID = "alarm_control_panel.elkm1_test_area"


def _build_entity(
    *, area_count: int = 1
) -> tuple[alarm_control_panel.ElkArea, MagicMock]:
    """Build a test ElkArea entity and backing area mock."""
    area = MagicMock()
    area.index = 0
    area.name = "Main Area"
    area.is_exit = False
    area.timer1 = 0
    area.timer2 = 0
    area.armed_status = ArmedStatus.DISARMED
    area.arm_up_state = ArmUpState.NOT_READY_TO_ARM
    area.alarm_state = AlarmState.NO_ALARM_ACTIVE
    area.in_alarm_state.return_value = False

    keypads = [MagicMock(), MagicMock()]
    users = MagicMock()
    users.username.return_value = "alice"

    elk = MagicMock()
    elk.areas.elements = [MagicMock() for _ in range(area_count)]
    elk.keypads = keypads
    elk.users = users
    elk.panel.elkm1_version = "1.0"

    elk_data = ELKM1Data(
        elk=elk,
        prefix="",
        mac="aa:bb:cc:dd:ee:ff",
        auto_configure=True,
        config={"temperature_unit": "F", "area": {"enabled": True}},
        keypads={},
    )

    return alarm_control_panel.ElkArea(area, elk, elk_data), area


async def _setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_elk_instance: MagicMock,
) -> None:
    """Set up the elkm1 integration for tests."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.elkm1.PLATFORMS",
            [Platform.ALARM_CONTROL_PANEL],
        ),
        patch("homeassistant.components.elkm1.async_discover_devices", return_value=[]),
        patch(
            "homeassistant.components.elkm1.async_discover_device", return_value=None
        ),
        patch("homeassistant.components.elkm1.Elk", return_value=mock_elk_instance),
        patch("homeassistant.components.elkm1.ElkSyncWaiter.async_wait"),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_setup_registers_alarm_entity_services(
    hass: HomeAssistant,
    alarm_mock_config_entry: MockConfigEntry,
    mock_elk_instance: MagicMock,
) -> None:
    """Test setup creates the alarm entity and custom services are callable."""
    await _setup_integration(hass, alarm_mock_config_entry, mock_elk_instance)

    assert hass.states.get(_ENTITY_ID)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ALARM_ARM_VACATION,
        {
            ATTR_ENTITY_ID: _ENTITY_ID,
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    mock_elk_instance.areas.elements[0].arm.assert_called_once_with(
        ArmLevel.ARMED_VACATION,
        1234,
    )


async def test_async_added_to_hass_registers_callbacks_and_restores_attributes() -> (
    None
):
    """Test callbacks are registered and restored attributes are loaded."""
    entity, area = _build_entity(area_count=1)
    entity.async_get_last_state = AsyncMock(
        return_value=State(
            "alarm_control_panel.main_area",
            AlarmControlPanelState.DISARMED,
            {
                ATTR_CHANGED_BY_KEYPAD: "hall keypad",
                ATTR_CHANGED_BY_TIME: "2026-06-05T12:00:00+00:00",
                ATTR_CHANGED_BY_ID: 4,
                ATTR_CHANGED_BY: "bob",
            },
        )
    )

    await entity.async_added_to_hass()

    area.add_callback.assert_has_calls(
        [call(entity._element_callback), call(entity._watch_area)]
    )
    for keypad in entity._elk.keypads:
        keypad.add_callback.assert_called_once_with(entity._watch_keypad)

    assert entity.changed_by == "bob"
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_KEYPAD] == "hall keypad"
    assert (
        entity.extra_state_attributes[ATTR_CHANGED_BY_TIME]
        == "2026-06-05T12:00:00+00:00"
    )
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_ID] == 4


async def test_async_added_to_hass_no_restore_when_no_prior_state() -> None:
    """Test that missing prior state leaves changed_by fields as None."""
    entity, _ = _build_entity(area_count=1)
    entity.async_get_last_state = AsyncMock(return_value=None)

    await entity.async_added_to_hass()

    assert entity.changed_by is None
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_KEYPAD] is None
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_TIME] is None
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_ID] is None


async def test_async_added_to_hass_skips_keypad_watch_with_multiple_areas() -> None:
    """Test keypad callbacks are skipped when panel has multiple areas."""
    entity, area = _build_entity(area_count=2)
    entity.async_get_last_state = AsyncMock(return_value=None)

    await entity.async_added_to_hass()

    area.add_callback.assert_has_calls(
        [call(entity._element_callback), call(entity._watch_area)]
    )
    for keypad in entity._elk.keypads:
        keypad.add_callback.assert_not_called()


def test_watch_keypad_updates_changed_by_data() -> None:
    """Test keypad updates set changed_by details for matching area/user."""
    entity, _ = _build_entity()
    entity.async_write_ha_state = MagicMock()

    class DummyKeypad:
        """Simple keypad object for testing."""

        def __init__(self, area: int, last_user: int | None) -> None:
            self.area = area
            self.last_user = last_user
            self.last_user_time = datetime(2026, 6, 5, 15, 0, tzinfo=UTC)
            self.name = "Front Door"

    with patch(
        "homeassistant.components.elkm1.alarm_control_panel.Keypad", DummyKeypad
    ):
        entity._watch_keypad(DummyKeypad(area=2, last_user=1), {"last_user": 1})
        entity._watch_keypad(DummyKeypad(area=0, last_user=None), {"last_user": None})

        keypad = DummyKeypad(area=0, last_user=3)
        entity._watch_keypad(keypad, {"last_user": 3})

    assert entity.changed_by == "alice"
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_KEYPAD] == "Front Door"
    assert (
        entity.extra_state_attributes[ATTR_CHANGED_BY_TIME]
        == "2026-06-05T15:00:00+00:00"
    )
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_ID] == 4
    entity.async_write_ha_state.assert_called_once()


def test_watch_area_updates_changed_by_data_from_log() -> None:
    """Test area log updates set changed_by details when user is present."""
    entity, _ = _build_entity()
    entity.async_write_ha_state = MagicMock()

    entity._watch_area(MagicMock(), {})
    entity._watch_area(MagicMock(), {"last_log": {"timestamp": "2026-06-05T16:00:00"}})
    entity._watch_area(
        MagicMock(),
        {
            "last_log": {
                "user_number": 2,
                "timestamp": "2026-06-05T16:00:00",
            }
        },
    )

    assert entity.changed_by == "alice"
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_KEYPAD] is None
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_TIME] == "2026-06-05T16:00:00"
    assert entity.extra_state_attributes[ATTR_CHANGED_BY_ID] == 2
    entity.async_write_ha_state.assert_called_once()


def test_properties_and_extra_state_attributes() -> None:
    """Test static properties and exported extra state attributes."""
    entity, area = _build_entity()
    area.is_exit = True
    area.timer1 = 12
    area.timer2 = 34
    area.armed_status = ArmedStatus.ARMED_AWAY
    area.arm_up_state = ArmUpState.FULLY_ARMED
    area.alarm_state = AlarmState.ENTRANCE_DELAY_ACTIVE
    entity._changed_by_keypad = "Kitchen"
    entity._changed_by_time = "2026-06-05T18:00:00"
    entity._changed_by_id = 7
    entity._changed_by = "charlie"
    entity._state = AlarmControlPanelState.ARMED_AWAY

    assert entity.code_format is CodeFormat.NUMBER
    assert entity.alarm_state is AlarmControlPanelState.ARMED_AWAY

    attrs = entity.extra_state_attributes
    assert attrs["index"] == 1
    assert attrs["is_exit"] is True
    assert attrs["timer1"] == 12
    assert attrs["timer2"] == 34
    assert attrs["armed_status"] == "armed_away"
    assert attrs["arm_up_state"] == "fully_armed"
    assert attrs["alarm_state"] == "entrance_delay_active"
    assert attrs[ATTR_CHANGED_BY_KEYPAD] == "Kitchen"
    assert attrs[ATTR_CHANGED_BY_TIME] == "2026-06-05T18:00:00"
    assert attrs[ATTR_CHANGED_BY_ID] == 7
    assert entity.changed_by == "charlie"


def test_extra_state_attributes_omits_none_enum_fields() -> None:
    """Test that None-valued enum fields are excluded from extra state attributes."""
    entity, area = _build_entity()
    area.armed_status = None
    area.arm_up_state = None
    area.alarm_state = None

    attrs = entity.extra_state_attributes

    assert "armed_status" not in attrs
    assert "arm_up_state" not in attrs
    assert "alarm_state" not in attrs


@pytest.mark.parametrize(
    (
        "alarm_state",
        "in_alarm",
        "timer1",
        "timer2",
        "is_exit",
        "armed_status",
        "expected",
    ),
    [
        pytest.param(None, False, 0, 0, False, None, None, id="alarm_state_none"),
        pytest.param(
            AlarmState.BURGLAR_ALARM,
            True,
            0,
            0,
            False,
            ArmedStatus.ARMED_AWAY,
            AlarmControlPanelState.TRIGGERED,
            id="triggered",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            20,
            0,
            True,
            ArmedStatus.ARMED_AWAY,
            AlarmControlPanelState.ARMING,
            id="arming_exit_timer",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            15,
            False,
            ArmedStatus.ARMED_AWAY,
            AlarmControlPanelState.PENDING,
            id="pending_entry_timer",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.DISARMED,
            AlarmControlPanelState.DISARMED,
            id="disarmed",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.ARMED_AWAY,
            AlarmControlPanelState.ARMED_AWAY,
            id="armed_away",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.ARMED_STAY,
            AlarmControlPanelState.ARMED_HOME,
            id="armed_stay",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.ARMED_STAY_INSTANT,
            AlarmControlPanelState.ARMED_HOME,
            id="armed_stay_instant",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.ARMED_TO_NIGHT,
            AlarmControlPanelState.ARMED_NIGHT,
            id="armed_to_night",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.ARMED_TO_NIGHT_INSTANT,
            AlarmControlPanelState.ARMED_NIGHT,
            id="armed_to_night_instant",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE,
            False,
            0,
            0,
            False,
            ArmedStatus.ARMED_TO_VACATION,
            AlarmControlPanelState.ARMED_VACATION,
            id="armed_to_vacation",
        ),
        pytest.param(
            AlarmState.NO_ALARM_ACTIVE, False, 0, 0, False, None, None, id="no_status"
        ),
    ],
)
def test_element_changed_state_mapping(
    alarm_state: AlarmState | None,
    in_alarm: bool,
    timer1: int,
    timer2: int,
    is_exit: bool,
    armed_status: ArmedStatus | None,
    expected: AlarmControlPanelState | None,
) -> None:
    """Test all main state mapping paths in _element_changed."""
    entity, area = _build_entity()
    area.alarm_state = alarm_state
    area.in_alarm_state.return_value = in_alarm
    area.timer1 = timer1
    area.timer2 = timer2
    area.is_exit = is_exit
    area.armed_status = armed_status

    entity._element_changed(area, {})

    assert entity.alarm_state is expected


def test_entry_exit_timer_is_running() -> None:
    """Test timer helper returns true when either entry/exit timer is active."""
    entity, area = _build_entity()

    area.timer1 = 0
    area.timer2 = 0
    assert entity._entry_exit_timer_is_running() is False

    area.timer1 = 1
    assert entity._entry_exit_timer_is_running() is True

    area.timer1 = 0
    area.timer2 = 1
    assert entity._entry_exit_timer_is_running() is True


async def test_alarm_command_methods() -> None:
    """Test all alarm command methods forward to the underlying area."""
    entity, area = _build_entity()

    await entity.async_alarm_disarm("1234")
    area.disarm.assert_called_once_with(1234)

    await entity.async_alarm_arm_home("1234")
    area.arm.assert_any_call(ArmLevel.ARMED_STAY, 1234)

    await entity.async_alarm_arm_away("1234")
    area.arm.assert_any_call(ArmLevel.ARMED_AWAY, 1234)

    await entity.async_alarm_arm_night("1234")
    area.arm.assert_any_call(ArmLevel.ARMED_NIGHT, 1234)

    await entity.async_alarm_arm_home_instant("1234")
    area.arm.assert_any_call(ArmLevel.ARMED_STAY_INSTANT, 1234)

    await entity.async_alarm_arm_night_instant("1234")
    area.arm.assert_any_call(ArmLevel.ARMED_NIGHT_INSTANT, 1234)

    await entity.async_alarm_arm_vacation("1234")
    area.arm.assert_any_call(ArmLevel.ARMED_VACATION, 1234)

    await entity.async_display_message(2, True, 10, "line 1", "line 2")
    area.display_message.assert_called_once_with(2, True, 10, "line 1", "line 2")

    await entity.async_bypass("1234")
    area.bypass.assert_called_once_with(1234)

    await entity.async_clear_bypass("1234")
    area.clear_bypass.assert_called_once_with(1234)


async def test_alarm_methods_ignore_missing_code() -> None:
    """Test code-dependent methods are no-ops when code is omitted."""
    entity, area = _build_entity()

    await entity.async_alarm_disarm(None)
    await entity.async_alarm_arm_home(None)
    await entity.async_alarm_arm_away(None)
    await entity.async_alarm_arm_night(None)
    await entity.async_alarm_arm_home_instant(None)
    await entity.async_alarm_arm_night_instant(None)
    await entity.async_alarm_arm_vacation(None)
    await entity.async_bypass(None)
    await entity.async_clear_bypass(None)

    area.disarm.assert_not_called()
    area.arm.assert_not_called()
    area.bypass.assert_not_called()
    area.clear_bypass.assert_not_called()
