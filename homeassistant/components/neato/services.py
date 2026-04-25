"""Neato services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_NAVIGATION = "navigation"
ATTR_CATEGORY = "category"
ATTR_ZONE = "zone"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "custom_cleaning",
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Optional(ATTR_MODE, default=2): cv.positive_int,
            vol.Optional(ATTR_NAVIGATION, default=1): cv.positive_int,
            vol.Optional(ATTR_CATEGORY, default=4): cv.positive_int,
            vol.Optional(ATTR_ZONE): cv.string,
        },
        func="neato_custom_cleaning",
    )
