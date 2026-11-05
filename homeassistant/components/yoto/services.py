"""Service actions for the Yoto integration."""

from datetime import timedelta

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SET_SLEEP_TIMER = "set_sleep_timer"
SERVICE_CLEAR_SLEEP_TIMER = "clear_sleep_timer"

ATTR_DURATION = "duration"
ATTR_END_OF_TRACK = "end_of_track"

SET_SLEEP_TIMER_SCHEMA = probatio.All(
    probatio.AtLeastOne(ATTR_DURATION, ATTR_END_OF_TRACK),
    cv.make_entity_service_schema(
        {
            probatio.Exclusive(ATTR_DURATION, "sleep_timer"): probatio.All(
                cv.time_period, probatio.Range(min=timedelta(seconds=1))
            ),
            probatio.Exclusive(ATTR_END_OF_TRACK, "sleep_timer"): True,
        }
    ),
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
