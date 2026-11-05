"""API key expiry reminders for the AEMET OpenData component."""

from datetime import date, datetime, timedelta
from functools import partial

from dateutil.relativedelta import relativedelta

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import (
    API_KEY_REMINDER_DAYS,
    API_KEY_URL,
    API_KEY_VALIDITY_MONTHS,
    CONF_API_KEY_DATE,
    CONF_API_KEY_REMINDER,
    DOMAIN,
)
from .util import parse_issue_date


def _notification_id(entry: ConfigEntry) -> str:
    """Return the persistent notification ID for an entry."""
    return f"{DOMAIN}_api_key_expiry_{entry.entry_id}"


@callback
def async_dismiss_api_key_reminder(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Dismiss the API key expiry notification for an entry."""
    persistent_notification.async_dismiss(hass, _notification_id(entry))


@callback
def _async_create_api_key_expiry_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
    expiry_date: date,
    _now: datetime | None = None,
) -> None:
    """Create the API key expiry notification."""
    persistent_notification.async_create(
        hass,
        (
            f"Your AEMET API key expires on {expiry_date.isoformat()}. "
            f"Request a new one at {API_KEY_URL} and update it in the "
            "integration options."
        ),
        title="AEMET API key expiring soon",
        notification_id=_notification_id(entry),
    )


@callback
def _async_handle_api_key_expired(
    hass: HomeAssistant,
    entry: ConfigEntry,
    _now: datetime | None = None,
) -> None:
    """Dismiss the reminder and request reauthentication for an expired key."""
    async_dismiss_api_key_reminder(hass, entry)
    entry.async_start_reauth(hass)


@callback
def async_schedule_api_key_reminder(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Schedule a reminder before the API key expires."""
    issue_date = parse_issue_date(entry.data.get(CONF_API_KEY_DATE))
    if issue_date is None:
        async_dismiss_api_key_reminder(hass, entry)
        return

    expiry_date = issue_date + relativedelta(months=API_KEY_VALIDITY_MONTHS)
    now = dt_util.now()

    if now.date() >= expiry_date:
        _async_handle_api_key_expired(hass, entry)
        return

    async_dismiss_api_key_reminder(hass, entry)

    entry.async_on_unload(
        async_track_point_in_utc_time(
            hass,
            partial(_async_handle_api_key_expired, hass, entry),
            dt_util.as_utc(dt_util.start_of_local_day(expiry_date)),
        )
    )

    if not entry.options.get(CONF_API_KEY_REMINDER, False):
        return

    reminder_date = expiry_date - timedelta(days=API_KEY_REMINDER_DAYS)
    reminder_dt = dt_util.start_of_local_day(reminder_date) + timedelta(hours=9)

    if now >= reminder_dt:
        _async_create_api_key_expiry_notification(hass, entry, expiry_date)
        return

    entry.async_on_unload(
        async_track_point_in_utc_time(
            hass,
            partial(
                _async_create_api_key_expiry_notification, hass, entry, expiry_date
            ),
            dt_util.as_utc(reminder_dt),
        )
    )
