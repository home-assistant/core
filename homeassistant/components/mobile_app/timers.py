"""Timers for the mobile app."""

from datetime import timedelta
from typing import Any

from homeassistant.components import notify
from homeassistant.components.intent import TimerEventType, TimerInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import device_action
from .const import (
    ATTR_APP_DATA,
    ATTR_LIVE_UPDATE,
    ATTR_START_LIVE_ACTIVITY_TOKEN,
    ATTR_TAG,
    CLEAR_NOTIFICATION,
)

TIMER_LIVE_ACTIVITY_ICON = "mdi:timer-outline"


@callback
def async_handle_timer_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event_type: TimerEventType,
    timer_info: TimerInfo,
) -> None:
    """Handle timer events."""
    if _supports_live_activity(entry):
        _async_handle_live_activity(hass, entry, event_type, timer_info)
        return

    if event_type != TimerEventType.FINISHED:
        return

    _async_send(
        hass,
        entry,
        timer_info,
        _finished_message(timer_info),
        {
            "group": "timers",
            # Android
            "channel": "Timers",
            "importance": "high",
            "ttl": 0,
            "priority": "high",
            # iOS
            "push": {
                "interruption-level": "time-sensitive",
            },
        },
    )


def _finished_message(timer_info: TimerInfo) -> str:
    """Return the message for a finished timer."""
    if timer_info.name:
        return f"{timer_info.name} finished"
    return f"{timedelta(seconds=timer_info.created_seconds)} timer finished"


def _supports_live_activity(entry: ConfigEntry) -> bool:
    """Return whether the app registered a token for starting Live Activities."""
    return bool(entry.data[ATTR_APP_DATA].get(ATTR_START_LIVE_ACTIVITY_TOKEN))


@callback
def _async_handle_live_activity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event_type: TimerEventType,
    timer_info: TimerInfo,
) -> None:
    """Mirror the timer in a Live Activity on the device."""
    tag = f"timer-{timer_info.id}"
    title = timer_info.name or "Timer"

    if event_type == TimerEventType.CANCELLED:
        _async_send(hass, entry, timer_info, CLEAR_NOTIFICATION, {ATTR_TAG: tag})
        return

    data: dict[str, Any] = {
        ATTR_TAG: tag,
        ATTR_LIVE_UPDATE: True,
        "notification_icon": TIMER_LIVE_ACTIVITY_ICON,
    }
    if event_type == TimerEventType.FINISHED:
        message = _finished_message(timer_info)
        data["chronometer"] = False
        # Not silent, so the end state alerts in place of the finished notification.
        # The push relay only adds a sound to an alert it is given.
        data["alert"] = {"title": title, "body": message}
        data["alert_sound"] = "default"
    else:
        seconds_left = timer_info.seconds_left
        if timer_info.is_active and not seconds_left:
            # Finished follows right away with the end state.
            return

        # The user just asked for this, so don't chime.
        data["silent"] = True
        duration = str(timedelta(seconds=timer_info.created_seconds))
        if timer_info.is_active:
            data["chronometer"] = True
            data["when"] = dt_util.utcnow().timestamp() + seconds_left
            data["when_relative"] = False
            message = f"{duration} timer"
        else:
            # The app draws a progress bar in place of the ticking one, so only send
            # it while paused.
            data["chronometer"] = False
            data["critical_text"] = "Paused"
            data["progress"] = seconds_left
            data["progress_max"] = timer_info.created_seconds
            message = f"Paused, {timedelta(seconds=seconds_left)} left"

    _async_send(hass, entry, timer_info, message, data, title=title)


@callback
def _async_send(
    hass: HomeAssistant,
    entry: ConfigEntry,
    timer_info: TimerInfo,
    message: str,
    data: dict[str, Any],
    title: str | None = None,
) -> None:
    """Send a notification to the device that set the timer."""
    config: dict[str, Any] = {
        CONF_DEVICE_ID: timer_info.device_id,
        notify.ATTR_MESSAGE: message,
        notify.ATTR_DATA: data,
    }
    if title is not None:
        config[notify.ATTR_TITLE] = title

    entry.async_create_task(
        hass,
        device_action.async_call_action_from_config(hass, config, {}, None),
        "mobile_app_timer_notification",
    )
