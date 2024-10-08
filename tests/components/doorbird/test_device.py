"""Test DoorBird device."""

from copy import deepcopy
from http import HTTPStatus

from doorbirdpy import DoorBirdScheduleEntry
import pytest

from homeassistant.components.doorbird.const import CONF_EVENTS
from homeassistant.core import HomeAssistant

from .conftest import DoorbirdMockerType


async def test_no_configured_events(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test a doorbird with no events configured."""
    await doorbird_mocker(options={CONF_EVENTS: []})
    assert not hass.states.async_all("event")


async def test_change_schedule_success(
    doorbird_mocker: DoorbirdMockerType,
    doorbird_schedule_wrong_param: list[DoorBirdScheduleEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a doorbird when change_schedule fails."""
    schedule_copy = deepcopy(doorbird_schedule_wrong_param)
    mock_doorbird = await doorbird_mocker(schedule=schedule_copy)
    assert "Unable to update schedule entry mydoorbird" not in caplog.text
    assert mock_doorbird.api.change_schedule.call_count == 1
    new_schedule: list[DoorBirdScheduleEntry] = (
        mock_doorbird.api.change_schedule.call_args[0]
    )
    # Ensure the attempt to update the schedule to fix the incorrect
    # param is made
    assert new_schedule[-1].output[-1].param == "1"


async def test_change_schedule_fails(
    doorbird_mocker: DoorbirdMockerType,
    doorbird_schedule_wrong_param: list[DoorBirdScheduleEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a doorbird when change_schedule fails."""
    schedule_copy = deepcopy(doorbird_schedule_wrong_param)
    mock_doorbird = await doorbird_mocker(
        schedule=schedule_copy, change_schedule=(False, HTTPStatus.UNAUTHORIZED)
    )
    assert "Unable to update schedule entry mydoorbird" in caplog.text
    assert mock_doorbird.api.change_schedule.call_count == 1
    new_schedule: list[DoorBirdScheduleEntry] = (
        mock_doorbird.api.change_schedule.call_args[0]
    )
    # Ensure the attempt to update the schedule to fix the incorrect
    # param is made
    assert new_schedule[-1].output[-1].param == "1"
