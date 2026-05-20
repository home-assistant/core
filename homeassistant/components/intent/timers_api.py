"""Timer websocket API."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import TIMER_DATA
from .timers import (
    TimerEventType,
    TimerInfo,
    TimerManager,
    TimerNotFoundError,
    TimersNotSupportedError,
    _get_total_seconds,
    _round_time,
)

_DURATION_FIELDS: dict[Any, Any] = {
    vol.Optional("hours"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("seconds"): vol.All(vol.Coerce(int), vol.Range(min=0)),
}
_REQUIRE_DURATION = cv.has_at_least_one_key("hours", "minutes", "seconds")


@callback
def async_register_timers_api(hass: HomeAssistant) -> None:
    """Register the timer websocket API."""
    websocket_api.async_register_command(hass, websocket_start_timer)
    websocket_api.async_register_command(hass, websocket_cancel_timer)
    websocket_api.async_register_command(hass, websocket_pause_timer)
    websocket_api.async_register_command(hass, websocket_unpause_timer)
    websocket_api.async_register_command(hass, websocket_increase_timer)
    websocket_api.async_register_command(hass, websocket_decrease_timer)
    websocket_api.async_register_command(hass, websocket_timer_status)
    websocket_api.async_register_command(hass, websocket_subscribe_timers)


@websocket_api.websocket_command(
    vol.All(
        vol.Schema(
            {
                vol.Required("type"): "intent/timers/start",
                vol.Required("device_id"): vol.Any(cv.string, None),
                **_DURATION_FIELDS,
                vol.Optional("name"): cv.string,
                vol.Optional("finished_event_data"): dict[str, Any],
            }
        ),
        _REQUIRE_DURATION,
    )
)
@websocket_api.async_response
async def websocket_start_timer(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Start a timer with a duration and optional name."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]

    try:
        timer_id = timer_manager.start_timer(
            device_id=msg["device_id"],
            hours=msg.get("hours"),
            minutes=msg.get("minutes"),
            seconds=msg.get("seconds"),
            language=hass.config.language,
            name=msg.get("name"),
            # Passed with EVENT_TIMER_FINISHED
            finished_event_data=msg.get("finished_event_data"),
        )
        connection.send_result(msg["id"], {"timer_id": timer_id})
    except (TimersNotSupportedError, ValueError) as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_SUPPORTED, str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intent/timers/cancel",
        vol.Required("timer_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_cancel_timer(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Cancel a timer."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    timer_id = msg["timer_id"]

    try:
        timer_manager.cancel_timer(timer_id)
        connection.send_result(msg["id"], {"timer_id": timer_id})
    except TimerNotFoundError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intent/timers/pause",
        vol.Required("timer_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_pause_timer(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Pause a timer."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    timer_id = msg["timer_id"]

    try:
        timer_manager.pause_timer(timer_id)
        connection.send_result(msg["id"], {"timer_id": timer_id})
    except TimerNotFoundError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intent/timers/unpause",
        vol.Required("timer_id"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_unpause_timer(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Unpause a timer."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    timer_id = msg["timer_id"]

    try:
        timer_manager.unpause_timer(timer_id)
        connection.send_result(msg["id"], {"timer_id": timer_id})
    except TimerNotFoundError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.websocket_command(
    vol.All(
        vol.Schema(
            {
                vol.Required("type"): "intent/timers/increase",
                vol.Required("timer_id"): cv.string,
                **_DURATION_FIELDS,
            }
        ),
        _REQUIRE_DURATION,
    )
)
@websocket_api.async_response
async def websocket_increase_timer(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Increase a timer's time."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    timer_id = msg["timer_id"]

    try:
        total_seconds = _get_total_seconds(
            {
                key: {"value": msg[key]}
                for key in ("hours", "minutes", "seconds")
                if key in msg
            }
        )
        timer_manager.add_time(timer_id, total_seconds)
        connection.send_result(msg["id"], {"timer_id": timer_id})
    except TimerNotFoundError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.websocket_command(
    vol.All(
        vol.Schema(
            {
                vol.Required("type"): "intent/timers/decrease",
                vol.Required("timer_id"): cv.string,
                **_DURATION_FIELDS,
            }
        ),
        _REQUIRE_DURATION,
    )
)
@websocket_api.async_response
async def websocket_decrease_timer(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Decrease a timer's time."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    timer_id = msg["timer_id"]

    try:
        total_seconds = _get_total_seconds(
            {
                key: {"value": msg[key]}
                for key in ("hours", "minutes", "seconds")
                if key in msg
            }
        )
        timer_manager.remove_time(timer_id, total_seconds)
        connection.send_result(msg["id"], {"timer_id": timer_id})
    except TimerNotFoundError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.websocket_command({vol.Required("type"): "intent/timers/status"})
@websocket_api.async_response
async def websocket_timer_status(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the status of all timers."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    statuses = _get_timer_statuses(timer_manager)
    connection.send_result(msg["id"], {"timers": statuses})


def _get_timer_statuses(timer_manager: TimerManager) -> list[dict[str, Any]]:
    """Get timer statuses for a list of timers."""
    statuses: list[dict[str, Any]] = []
    for timer in timer_manager.timers.values():
        total_seconds = timer.seconds_left

        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        # Get lower-precision time for feedback
        rounded_hours, rounded_minutes, rounded_seconds = _round_time(
            hours, minutes, seconds
        )

        statuses.append(
            {
                ATTR_ID: timer.id,
                ATTR_NAME: timer.name or "",
                ATTR_DEVICE_ID: timer.device_id or "",
                "language": timer.language,
                "start_hours": timer.start_hours or 0,
                "start_minutes": timer.start_minutes or 0,
                "start_seconds": timer.start_seconds or 0,
                "is_active": timer.is_active,
                "hours_left": hours,
                "minutes_left": minutes,
                "seconds_left": seconds,
                "rounded_hours_left": rounded_hours,
                "rounded_minutes_left": rounded_minutes,
                "rounded_seconds_left": rounded_seconds,
                "total_seconds_left": total_seconds,
            }
        )

    return statuses


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intent/timers/subscribe",
    }
)
@websocket_api.async_response
async def websocket_subscribe_timers(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to intent timers."""
    msg_id = msg["id"]

    timer_manager: TimerManager = hass.data[TIMER_DATA]

    def send_event(event_type: TimerEventType, timer: TimerInfo) -> None:
        """Send a timer event."""
        connection.send_event(
            msg_id,
            {
                "event_type": event_type,
                "timer": timer.dict_repr,
            },
        )

    connection.subscriptions[msg_id] = timer_manager.register_listener(send_event)

    # Current timers
    timers = [timer.dict_repr for timer in timer_manager.timers.values()]
    connection.send_result(msg_id, {"timers": timers})
