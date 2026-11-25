"""Actions for timer lists."""

from typing import Any

import probatio

from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DURATION,
    ATTR_STATUS,
    ATTR_TIMER_ID,
    ATTR_TIMERS,
    DATA_COMPONENT,
    TimerListEntityFeature,
    TimerListService,
    TimerStatus,
)
from .entity import TimerListEntity


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up timer list actions."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        TimerListService.CREATE_TIMER,
        {
            probatio.Optional(ATTR_NAME): cv.string,
            probatio.Required(ATTR_DURATION): cv.positive_time_period,
        },
        _async_create_timer,
        required_features=[TimerListEntityFeature.CREATE_TIMER],
        supports_response=SupportsResponse.OPTIONAL,
    )
    component.async_register_entity_service(
        TimerListService.PAUSE_TIMER,
        {probatio.Required(ATTR_TIMER_ID): cv.string},
        "async_pause_timer",
        required_features=[TimerListEntityFeature.PAUSE_TIMER],
    )
    component.async_register_entity_service(
        TimerListService.UNPAUSE_TIMER,
        {probatio.Required(ATTR_TIMER_ID): cv.string},
        "async_unpause_timer",
        required_features=[TimerListEntityFeature.PAUSE_TIMER],
    )
    component.async_register_entity_service(
        TimerListService.CANCEL_TIMER,
        {probatio.Required(ATTR_TIMER_ID): cv.string},
        "async_cancel_timer",
        required_features=[TimerListEntityFeature.CANCEL_TIMER],
    )
    component.async_register_entity_service(
        TimerListService.FINISH_TIMER,
        {probatio.Required(ATTR_TIMER_ID): cv.string},
        "async_finish_timer",
        required_features=[TimerListEntityFeature.FINISH_TIMER],
    )
    component.async_register_entity_service(
        TimerListService.ADD_TIME,
        {
            probatio.Required(ATTR_TIMER_ID): cv.string,
            probatio.Required(ATTR_DURATION): cv.positive_time_period,
        },
        _async_add_time,
        required_features=[TimerListEntityFeature.ADD_TIME],
    )
    component.async_register_entity_service(
        TimerListService.SUBTRACT_TIME,
        {
            probatio.Required(ATTR_TIMER_ID): cv.string,
            probatio.Required(ATTR_DURATION): cv.positive_time_period,
        },
        _async_subtract_time,
        required_features=[TimerListEntityFeature.ADD_TIME],
    )
    component.async_register_entity_service(
        TimerListService.REMOVE_TIMER,
        {probatio.Required(ATTR_TIMER_ID): cv.string},
        "async_remove_timer",
        required_features=[TimerListEntityFeature.REMOVE_TIMER],
    )
    component.async_register_entity_service(
        TimerListService.GET_TIMERS,
        {
            probatio.Optional(ATTR_STATUS): probatio.All(
                probatio.EnsureList(), [probatio.Coerce(TimerStatus)]
            )
        },
        _async_get_timers,
        supports_response=SupportsResponse.ONLY,
    )


async def _async_create_timer(
    entity: TimerListEntity, call: ServiceCall
) -> dict[str, Any]:
    """Handle the create_timer service."""
    timer_id = await entity.async_create_timer(
        name=call.data.get(ATTR_NAME),
        duration=call.data[ATTR_DURATION],
    )
    return {ATTR_TIMER_ID: timer_id}


async def _async_add_time(entity: TimerListEntity, call: ServiceCall) -> None:
    """Handle the add_time service."""
    await entity.async_add_time(call.data[ATTR_TIMER_ID], call.data[ATTR_DURATION])


async def _async_subtract_time(entity: TimerListEntity, call: ServiceCall) -> None:
    """Handle the subtract_time service."""
    await entity.async_add_time(call.data[ATTR_TIMER_ID], -call.data[ATTR_DURATION])


async def _async_get_timers(
    entity: TimerListEntity, call: ServiceCall
) -> dict[str, Any]:
    """Handle the get_timers service."""
    now = dt_util.utcnow()
    statuses: list[TimerStatus] | None = call.data.get(ATTR_STATUS)
    return {
        ATTR_TIMERS: [
            timer.as_dict(now)
            for timer in entity.timers
            if not statuses or timer.status in statuses
        ]
    }
