"""Define tests for the AEMET OpenData API key reminders."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aemet.const import (
    CONF_API_KEY_DATE,
    CONF_API_KEY_REMINDER,
    DOMAIN,
)
from homeassistant.components.aemet.reminder import async_schedule_api_key_reminder
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

REMINDER_MODULE = "homeassistant.components.aemet.reminder"
DISMISS = f"{REMINDER_MODULE}.persistent_notification.async_dismiss"
CREATE = f"{REMINDER_MODULE}.persistent_notification.async_create"
TRACK = f"{REMINDER_MODULE}.async_track_point_in_utc_time"


def _create_entry(
    reminder: bool, issue_date: str | None = "2021-01-01"
) -> MockConfigEntry:
    """Create a mock config entry."""
    data: dict[str, str] = {}
    if issue_date is not None:
        data[CONF_API_KEY_DATE] = issue_date
    return MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options={CONF_API_KEY_REMINDER: reminder},
    )


async def test_reminder_is_scheduled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the expiry and reminder are scheduled."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    entry = _create_entry(reminder=True)
    entry.add_to_hass(hass)

    with (
        patch(DISMISS) as dismiss,
        patch(CREATE) as create,
        patch(TRACK) as track,
    ):
        async_schedule_api_key_reminder(hass, entry)

    dismiss.assert_called_once()
    create.assert_not_called()
    assert [call.args[2] for call in track.call_args_list] == [
        dt_util.as_utc(dt_util.start_of_local_day(datetime(2021, 4, 1))),
        dt_util.as_utc(
            dt_util.start_of_local_day(datetime(2021, 3, 29)) + timedelta(hours=9)
        ),
    ]


async def test_reminder_is_created_inside_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the notification is created when inside the reminder window."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-03-30 12:00:00+00:00")
    entry = _create_entry(reminder=True)
    entry.add_to_hass(hass)

    with (
        patch(DISMISS),
        patch(CREATE) as create,
        patch(TRACK) as track,
    ):
        async_schedule_api_key_reminder(hass, entry)

    create.assert_called_once()
    assert track.call_count == 1


@pytest.mark.parametrize("reminder_enabled", [False, True])
async def test_expired_key_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reminder_enabled: bool,
) -> None:
    """Test an expired key starts reauthentication."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-04-02 12:00:00+00:00")
    entry = _create_entry(reminder=reminder_enabled)
    entry.add_to_hass(hass)

    with (
        patch(DISMISS) as dismiss,
        patch(CREATE) as create,
        patch(TRACK) as track,
        patch.object(ConfigEntry, "async_start_reauth") as start_reauth,
    ):
        async_schedule_api_key_reminder(hass, entry)

    dismiss.assert_called_once()
    create.assert_not_called()
    track.assert_not_called()
    start_reauth.assert_called_once_with(hass)


async def test_disabled_reminder(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a disabled reminder schedules expiry without a notification."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-03-30 12:00:00+00:00")
    entry = _create_entry(reminder=False)
    entry.add_to_hass(hass)

    with (
        patch(DISMISS) as dismiss,
        patch(CREATE) as create,
        patch(TRACK) as track,
    ):
        async_schedule_api_key_reminder(hass, entry)

    dismiss.assert_called_once()
    create.assert_not_called()
    assert [call.args[2] for call in track.call_args_list] == [
        dt_util.as_utc(dt_util.start_of_local_day(datetime(2021, 4, 1))),
    ]


async def test_missing_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a missing issue date does not schedule anything."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    entry = _create_entry(reminder=True, issue_date=None)
    entry.add_to_hass(hass)

    with (
        patch(DISMISS) as dismiss,
        patch(CREATE) as create,
        patch(TRACK) as track,
    ):
        async_schedule_api_key_reminder(hass, entry)

    dismiss.assert_called_once()
    create.assert_not_called()
    track.assert_not_called()
