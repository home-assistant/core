"""Timers for the mobile app."""

from datetime import timedelta

from homeassistant.components import notify
from homeassistant.components.timer_list import TimerListEvent, TimerListEventType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback

from . import device_action


@callback
def async_handle_timer_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_id: str,
    event: TimerListEvent,
) -> None:
    """Handle timer events."""
    if event.event_type != TimerListEventType.FINISHED:
        return

    item = event.item
    if item.name:
        message = f"{item.name} finished"
    else:
        duration = timedelta(seconds=int(item.duration.total_seconds()))
        message = f"{duration} timer finished"

    entry.async_create_task(
        hass,
        device_action.async_call_action_from_config(
            hass,
            {
                CONF_DEVICE_ID: device_id,
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
