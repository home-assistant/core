"""Rain Bird Irrigation system services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import ATTR_DURATION, DOMAIN

SERVICE_START_IRRIGATION = "start_irrigation"

SERVICE_SCHEMA_IRRIGATION: VolDictType = {
    vol.Required(ATTR_DURATION): cv.positive_float,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_IRRIGATION,
        entity_domain=SWITCH_DOMAIN,
        schema=SERVICE_SCHEMA_IRRIGATION,
        func="async_turn_on",
    )
