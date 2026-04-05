"""Tests for Envisalink alarm control panel."""

from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.envisalink.alarm_control_panel import EnvisalinkAlarm
from homeassistant.core import HomeAssistant

PARTITION = 1


def _make_status(
    *,
    disarmed: bool = False,
    last_disarmed_by_user: int = 0,
    last_armed_by_user: int = 0,
) -> dict[str, Any]:
    """Build a minimal pyenvisalink-style partition status dict."""
    return {
        "alarm": False,
        "armed_zero_entry_delay": False,
        "armed_away": False,
        "armed_stay": False,
        "exit_delay": False,
        "entry_delay": False,
        "alpha": disarmed,
        "last_disarmed_by_user": last_disarmed_by_user,
        "last_armed_by_user": last_armed_by_user,
    }


def _make_alarm(
    hass: HomeAssistant,
    *,
    status: dict[str, Any] | None = None,
) -> EnvisalinkAlarm:
    """Instantiate an EnvisalinkAlarm with a mocked controller."""
    if status is None:
        status = _make_status(disarmed=True)
    info: dict[str, Any] = {"status": status}
    alarm = EnvisalinkAlarm(
        partition_number=PARTITION,
        alarm_name="Test Alarm",
        code=None,
        panic_type="Police",
        info=info,
        controller=MagicMock(),
    )
    alarm.hass = hass
    return alarm


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


async def test_extra_state_attributes_with_user(hass: HomeAssistant) -> None:
    """Raw user IDs are returned when the panel reports a nonzero slot."""
    alarm = _make_alarm(
        hass,
        status=_make_status(
            disarmed=True, last_disarmed_by_user=2, last_armed_by_user=3
        ),
    )

    attrs = alarm.extra_state_attributes

    assert attrs["last_disarmed_by_user_id"] == 2
    assert attrs["last_armed_by_user_id"] == 3


async def test_extra_state_attributes_no_user(hass: HomeAssistant) -> None:
    """Both fields are None when the panel reports slot 0 (no user recorded)."""
    alarm = _make_alarm(
        hass,
        status=_make_status(
            disarmed=True, last_disarmed_by_user=0, last_armed_by_user=0
        ),
    )

    attrs = alarm.extra_state_attributes

    assert attrs["last_disarmed_by_user_id"] is None
    assert attrs["last_armed_by_user_id"] is None
