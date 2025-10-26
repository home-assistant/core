"""Timers for the mobile app."""

from datetime import timedelta

from homeassistant.components import notify
from homeassistant.components.intent import TimerEventType, TimerInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback

from . import device_action


@callback
def async_handle_timer_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event_type: TimerEventType,
    timer_info: TimerInfo,
) -> None:
    """Handle timer events."""
    if event_type != TimerEventType.FINISHED:
        return

    if timer_info.name:
        message = f"{timer_info.name} finished"
    else:
        message = f"{timedelta(seconds=timer_info.created_seconds)} timer finished"

    entry.async_create_task(
        hass,
        device_action.async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: timer_info.device_id,
                notify.ATTR_MESSAGE: message,
                notify.ATTR_DATA: {
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
            },
            {},
            None,
        ),
        "mobile_app_timer_notification",
    )
