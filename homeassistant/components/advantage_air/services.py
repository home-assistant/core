"""Services for Advantage Air integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ADVANTAGE_AIR_SERVICE_SET_TIME_TO = "set_time_to"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        entity_domain=SENSOR_DOMAIN,
        schema={vol.Required("minutes"): cv.positive_int},
        func="set_time_to",
    )
