"""WebSocket API for Matter lock schedule management."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .adapter import MatterAdapter
from .api_base import (
    DEVICE_ID,
    ID,
    TYPE,
    async_get_matter_adapter,
    async_get_node,
    async_handle_failed_command,
)
from .helpers import (
    get_lock_endpoint_from_node,
    lock_supports_holiday_schedules,
    lock_supports_week_day_schedules,
    lock_supports_year_day_schedules,
)

ERROR_LOCK_NOT_FOUND = "lock_not_found"
ERROR_WEEK_DAY_SCHEDULES_NOT_SUPPORTED = "week_day_schedules_not_supported"
ERROR_YEAR_DAY_SCHEDULES_NOT_SUPPORTED = "year_day_schedules_not_supported"
ERROR_HOLIDAY_SCHEDULES_NOT_SUPPORTED = "holiday_schedules_not_supported"
ERROR_SCHEDULE_NOT_FOUND = "schedule_not_found"
ERROR_INVALID_TIME_RANGE = "invalid_time_range"


class LockNotFound(Exception):
    """Exception raised when a lock endpoint is not found on a node."""


class WeekDaySchedulesNotSupported(Exception):
    """Exception raised when lock does not support week day schedules."""


class YearDaySchedulesNotSupported(Exception):
    """Exception raised when lock does not support year day schedules."""


class HolidaySchedulesNotSupported(Exception):
    """Exception raised when lock does not support holiday schedules."""


class ScheduleNotFound(Exception):
    """Exception raised when a schedule is not found."""

    def __init__(self, schedule_index: int) -> None:
        """Initialize the exception."""
        super().__init__(f"Schedule at index {schedule_index} was not found")
        self.schedule_index = schedule_index


class InvalidTimeRange(Exception):
    """Exception raised when time range is invalid."""


# Operating mode mapping for holiday schedules
OPERATING_MODE_MAP = {
    0: "normal",
    1: "vacation",
    2: "privacy",
    3: "no_remote_lock_unlock",
    4: "passage",
}
OPERATING_MODE_REVERSE_MAP = {v: k for k, v in OPERATING_MODE_MAP.items()}

# Day names for days mask
DAY_NAMES = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
]


def _days_mask_to_list(days_mask: int) -> list[str]:
    """Convert a days mask bitmap to a list of day names."""
    days = []
    for i, day_name in enumerate(DAY_NAMES):
        if days_mask & (1 << i):
            days.append(day_name)
    return days


def async_handle_schedule_errors[**_P](
    func: Callable[
        Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    Concatenate[HomeAssistant, ActiveConnection, dict[str, Any], _P],
    Coroutine[Any, Any, None],
]:
    """Decorate function to handle schedule-specific errors."""

    @wraps(func)
    async def async_handle_schedule_errors_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Handle schedule-specific errors."""
        try:
            await func(hass, connection, msg, *args, **kwargs)
        except LockNotFound:
            connection.send_error(
                msg[ID], ERROR_LOCK_NOT_FOUND, "No lock endpoint found on this device"
            )
        except WeekDaySchedulesNotSupported:
            connection.send_error(
                msg[ID],
                ERROR_WEEK_DAY_SCHEDULES_NOT_SUPPORTED,
                "Lock does not support week day schedules",
            )
        except YearDaySchedulesNotSupported:
            connection.send_error(
                msg[ID],
                ERROR_YEAR_DAY_SCHEDULES_NOT_SUPPORTED,
                "Lock does not support year day schedules",
            )
        except HolidaySchedulesNotSupported:
            connection.send_error(
                msg[ID],
                ERROR_HOLIDAY_SCHEDULES_NOT_SUPPORTED,
                "Lock does not support holiday schedules",
            )
        except ScheduleNotFound as err:
            connection.send_error(
                msg[ID],
                ERROR_SCHEDULE_NOT_FOUND,
                f"Schedule at index {err.schedule_index} was not found",
            )
        except InvalidTimeRange:
            connection.send_error(
                msg[ID],
                ERROR_INVALID_TIME_RANGE,
                "Invalid time range: end time must be after start time",
            )

    return async_handle_schedule_errors_func


@callback
def async_register_lock_schedules_api(hass: HomeAssistant) -> None:
    """Register lock schedule management API endpoints."""
    # Week Day Schedule commands
    websocket_api.async_register_command(hass, websocket_set_week_day_schedule)
    websocket_api.async_register_command(hass, websocket_get_week_day_schedule)
    websocket_api.async_register_command(hass, websocket_clear_week_day_schedule)
    # Year Day Schedule commands
    websocket_api.async_register_command(hass, websocket_set_year_day_schedule)
    websocket_api.async_register_command(hass, websocket_get_year_day_schedule)
    websocket_api.async_register_command(hass, websocket_clear_year_day_schedule)
    # Holiday Schedule commands
    websocket_api.async_register_command(hass, websocket_set_holiday_schedule)
    websocket_api.async_register_command(hass, websocket_get_holiday_schedule)
    websocket_api.async_register_command(hass, websocket_clear_holiday_schedule)


# =============================================================================
# Week Day Schedule Commands
# =============================================================================


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/set_week_day_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("week_day_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("days_mask"): vol.All(vol.Coerce(int), vol.Range(min=1, max=127)),
        vol.Required("start_hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Required("start_minute"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=59)
        ),
        vol.Required("end_hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Required("end_minute"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_set_week_day_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Set a week day schedule for a user on the lock.

    The days_mask is a bitmap where:
    - Bit 0: Sunday
    - Bit 1: Monday
    - Bit 2: Tuesday
    - Bit 3: Wednesday
    - Bit 4: Thursday
    - Bit 5: Friday
    - Bit 6: Saturday

    Example: 62 (0b111110) = Monday through Friday
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_week_day_schedules(lock_endpoint):
        raise WeekDaySchedulesNotSupported

    # Validate time range
    start_minutes = msg["start_hour"] * 60 + msg["start_minute"]
    end_minutes = msg["end_hour"] * 60 + msg["end_minute"]
    if end_minutes <= start_minutes:
        raise InvalidTimeRange

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetWeekDaySchedule(
            weekDayIndex=msg["week_day_index"],
            userIndex=msg["user_index"],
            daysMask=msg["days_mask"],
            startHour=msg["start_hour"],
            startMinute=msg["start_minute"],
            endHour=msg["end_hour"],
            endMinute=msg["end_minute"],
        ),
    )

    connection.send_result(
        msg[ID],
        {
            "week_day_index": msg["week_day_index"],
            "user_index": msg["user_index"],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_week_day_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("week_day_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_week_day_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get a week day schedule from the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_week_day_schedules(lock_endpoint):
        raise WeekDaySchedulesNotSupported

    response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetWeekDaySchedule(
            weekDayIndex=msg["week_day_index"],
            userIndex=msg["user_index"],
        ),
    )

    # Check if schedule exists (status 0 = success)
    if response["status"] != 0:
        raise ScheduleNotFound(msg["week_day_index"])

    connection.send_result(
        msg[ID],
        {
            "week_day_index": response["weekDayIndex"],
            "user_index": response["userIndex"],
            "status": "occupied",
            "days_mask": response["daysMask"],
            "days": _days_mask_to_list(response["daysMask"]),
            "start_hour": response["startHour"],
            "start_minute": response["startMinute"],
            "end_hour": response["endHour"],
            "end_minute": response["endMinute"],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_week_day_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("week_day_index"): vol.All(
            vol.Coerce(int), vol.Any(vol.Range(min=1), 0xFE)
        ),
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_clear_week_day_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Clear a week day schedule from the lock.

    Use week_day_index 0xFE (254) to clear all schedules for the user.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_week_day_schedules(lock_endpoint):
        raise WeekDaySchedulesNotSupported

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearWeekDaySchedule(
            weekDayIndex=msg["week_day_index"],
            userIndex=msg["user_index"],
        ),
    )

    connection.send_result(msg[ID])


# =============================================================================
# Year Day Schedule Commands
# =============================================================================


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/set_year_day_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("year_day_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("local_start_time"): vol.Coerce(int),
        vol.Required("local_end_time"): vol.Coerce(int),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_set_year_day_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Set a year day schedule for a user on the lock.

    The local_start_time and local_end_time are epoch seconds representing
    the start and end of the date range during which the user has access.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_year_day_schedules(lock_endpoint):
        raise YearDaySchedulesNotSupported

    # Validate time range
    if msg["local_end_time"] <= msg["local_start_time"]:
        raise InvalidTimeRange

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetYearDaySchedule(
            yearDayIndex=msg["year_day_index"],
            userIndex=msg["user_index"],
            localStartTime=msg["local_start_time"],
            localEndTime=msg["local_end_time"],
        ),
    )

    connection.send_result(
        msg[ID],
        {
            "year_day_index": msg["year_day_index"],
            "user_index": msg["user_index"],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_year_day_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("year_day_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_year_day_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get a year day schedule from the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_year_day_schedules(lock_endpoint):
        raise YearDaySchedulesNotSupported

    response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetYearDaySchedule(
            yearDayIndex=msg["year_day_index"],
            userIndex=msg["user_index"],
        ),
    )

    # Check if schedule exists (status 0 = success)
    if response["status"] != 0:
        raise ScheduleNotFound(msg["year_day_index"])

    connection.send_result(
        msg[ID],
        {
            "year_day_index": response["yearDayIndex"],
            "user_index": response["userIndex"],
            "status": "occupied",
            "local_start_time": response["localStartTime"],
            "local_end_time": response["localEndTime"],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_year_day_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("year_day_index"): vol.All(
            vol.Coerce(int), vol.Any(vol.Range(min=1), 0xFE)
        ),
        vol.Required("user_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_clear_year_day_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Clear a year day schedule from the lock.

    Use year_day_index 0xFE (254) to clear all schedules for the user.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_year_day_schedules(lock_endpoint):
        raise YearDaySchedulesNotSupported

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearYearDaySchedule(
            yearDayIndex=msg["year_day_index"],
            userIndex=msg["user_index"],
        ),
    )

    connection.send_result(msg[ID])


# =============================================================================
# Holiday Schedule Commands
# =============================================================================


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/set_holiday_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("holiday_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("local_start_time"): vol.Coerce(int),
        vol.Required("local_end_time"): vol.Coerce(int),
        vol.Required("operating_mode"): vol.In(OPERATING_MODE_REVERSE_MAP.keys()),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_set_holiday_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Set a holiday schedule on the lock.

    Holiday schedules are device-wide (not per-user) and define time periods
    during which the lock operates in a different mode.

    Operating modes:
    - normal: Normal operation
    - vacation: Vacation mode
    - privacy: Privacy mode (no RF operation)
    - no_remote_lock_unlock: No remote lock/unlock allowed
    - passage: Passage mode (unlocked)
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_holiday_schedules(lock_endpoint):
        raise HolidaySchedulesNotSupported

    # Validate time range
    if msg["local_end_time"] <= msg["local_start_time"]:
        raise InvalidTimeRange

    operating_mode = OPERATING_MODE_REVERSE_MAP.get(msg["operating_mode"], 0)

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.SetHolidaySchedule(
            holidayIndex=msg["holiday_index"],
            localStartTime=msg["local_start_time"],
            localEndTime=msg["local_end_time"],
            operatingMode=operating_mode,
        ),
    )

    connection.send_result(
        msg[ID],
        {
            "holiday_index": msg["holiday_index"],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/get_holiday_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("holiday_index"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_get_holiday_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Get a holiday schedule from the lock."""
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_holiday_schedules(lock_endpoint):
        raise HolidaySchedulesNotSupported

    response = await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.GetHolidaySchedule(
            holidayIndex=msg["holiday_index"],
        ),
    )

    # Check if schedule exists (status 0 = success)
    if response["status"] != 0:
        raise ScheduleNotFound(msg["holiday_index"])

    connection.send_result(
        msg[ID],
        {
            "holiday_index": response["holidayIndex"],
            "status": "occupied",
            "local_start_time": response["localStartTime"],
            "local_end_time": response["localEndTime"],
            "operating_mode": OPERATING_MODE_MAP.get(
                response["operatingMode"], "unknown"
            ),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/lock/clear_holiday_schedule",
        vol.Required(DEVICE_ID): str,
        vol.Required("holiday_index"): vol.All(
            vol.Coerce(int), vol.Any(vol.Range(min=1), 0xFE)
        ),
    }
)
@websocket_api.async_response
@async_handle_schedule_errors
@async_handle_failed_command
@async_get_matter_adapter
@async_get_node
async def websocket_clear_holiday_schedule(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
    node: MatterNode,
) -> None:
    """Clear a holiday schedule from the lock.

    Use holiday_index 0xFE (254) to clear all holiday schedules.
    """
    lock_endpoint = get_lock_endpoint_from_node(node)
    if lock_endpoint is None:
        raise LockNotFound

    if not lock_supports_holiday_schedules(lock_endpoint):
        raise HolidaySchedulesNotSupported

    await matter.matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=lock_endpoint.endpoint_id,
        command=clusters.DoorLock.Commands.ClearHolidaySchedule(
            holidayIndex=msg["holiday_index"],
        ),
    )

    connection.send_result(msg[ID])
