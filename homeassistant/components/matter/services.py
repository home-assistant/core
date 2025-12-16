"""Services for Matter devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.const import Platform # Added Platform import

from .const import DOMAIN

ATTR_DURATION = "duration"
ATTR_EMERGENCY_BOOST = "emergency_boost"
ATTR_TEMPORARY_SETPOINT = "temporary_setpoint"
ATTR_CODE_SLOT = "code_slot" # Added
ATTR_USERCODE = "usercode" # Added

SERVICE_WATER_HEATER_BOOST = "water_heater_boost"
SERVICE_SET_LOCK_USERCODE = "set_lock_usercode" # Added
SERVICE_CLEAR_LOCK_USERCODE = "clear_lock_usercode" # Added


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Matter services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_WATER_HEATER_BOOST,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            # duration >=1
            vol.Required(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(ATTR_EMERGENCY_BOOST): cv.boolean,
            vol.Optional(ATTR_TEMPORARY_SETPOINT): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LOCK_USERCODE,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required(ATTR_CODE_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
            vol.Required(ATTR_USERCODE): cv.string,
        },
        func="async_set_usercode",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_LOCK_USERCODE,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required(ATTR_CODE_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
        },
        func="async_clear_usercode",
    )

