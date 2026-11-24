"""Service actions for the Yoto integration."""

from datetime import timedelta
from enum import StrEnum
from typing import Any

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SleepTimerMode


class YotoService(StrEnum):
    """Store keys for Yoto services."""

    CLEAR_SLEEP_TIMER = "clear_sleep_timer"
    SET_SLEEP_TIMER = "set_sleep_timer"


class YotoServiceArgument(StrEnum):
    """Store keys for Yoto service arguments."""

    DURATION = "duration"
    MODE = "mode"


def _validate_duration(data: dict[str, Any]) -> dict[str, Any]:
    """Require a duration in duration mode, and only there."""
    if data[YotoServiceArgument.MODE] is SleepTimerMode.DURATION:
        if YotoServiceArgument.DURATION not in data:
            raise probatio.Invalid(
                "duration is required in duration mode", [YotoServiceArgument.DURATION]
            )
    elif YotoServiceArgument.DURATION in data:
        raise probatio.Invalid(
            "duration cannot be used in end of track mode",
            [YotoServiceArgument.DURATION],
        )
    return data


SET_SLEEP_TIMER_SCHEMA = probatio.All(
    cv.make_entity_service_schema(
        {
            probatio.Optional(
                YotoServiceArgument.MODE, default=SleepTimerMode.DURATION
            ): probatio.Coerce(SleepTimerMode),
            probatio.Optional(YotoServiceArgument.DURATION): probatio.All(
                cv.time_period, probatio.Range(min=timedelta(seconds=1))
            ),
        }
    ),
    _validate_duration,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Yoto service actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YotoService.SET_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SET_SLEEP_TIMER_SCHEMA,
        func="async_set_sleep_timer",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YotoService.CLEAR_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_clear_sleep_timer",
    )
