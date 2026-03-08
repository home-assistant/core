"""Litter-Robot services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SET_SLEEP_MODE = "set_sleep_mode"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SLEEP_MODE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required("enabled"): cv.boolean,
            vol.Optional("start_time"): cv.time,
        },
        func="async_set_sleep_mode",
    )
