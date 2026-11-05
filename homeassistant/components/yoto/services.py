"""Service actions for the Yoto integration."""

from datetime import timedelta
from typing import Any

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SleepTimerMode

SERVICE_SET_SLEEP_TIMER = "set_sleep_timer"
SERVICE_CLEAR_SLEEP_TIMER = "clear_sleep_timer"

ATTR_MODE = "mode"
ATTR_DURATION = "duration"


def _validate_duration(data: dict[str, Any]) -> dict[str, Any]:
    """Require a duration in duration mode, and only there."""
    if data[ATTR_MODE] is SleepTimerMode.DURATION:
        if ATTR_DURATION not in data:
            raise probatio.Invalid(
                "duration is required in duration mode", [ATTR_DURATION]
            )
    elif ATTR_DURATION in data:
        raise probatio.Invalid(
            "duration cannot be used in end of track mode", [ATTR_DURATION]
        )
    return data


SET_SLEEP_TIMER_SCHEMA = probatio.All(
    cv.make_entity_service_schema(
        {
            probatio.Optional(
                ATTR_MODE, default=SleepTimerMode.DURATION
            ): probatio.Coerce(SleepTimerMode),
            probatio.Optional(ATTR_DURATION): probatio.All(
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
        SERVICE_SET_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SET_SLEEP_TIMER_SCHEMA,
        func="async_set_sleep_timer",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_SLEEP_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_clear_sleep_timer",
    )
