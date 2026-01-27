"""Services for Matter devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_DURATION = "duration"
ATTR_EMERGENCY_BOOST = "emergency_boost"
ATTR_TEMPORARY_SETPOINT = "temporary_setpoint"
ATTR_CODE_SLOT = "code_slot"
ATTR_USERCODE = "usercode"
ATTR_USER_INDEX = "user_index"
ATTR_CREDENTIAL_TYPE = "credential_type"
ATTR_CREDENTIAL_INDEX = "credential_index"

SERVICE_WATER_HEATER_BOOST = "water_heater_boost"
SERVICE_SET_LOCK_USERCODE = "set_lock_usercode"
SERVICE_CLEAR_LOCK_USERCODE = "clear_lock_usercode"
SERVICE_GET_LOCK_USER = "get_lock_user"
SERVICE_GET_CREDENTIAL_STATUS = "get_credential_status"


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
            vol.Required(ATTR_CODE_SLOT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
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
            vol.Required(ATTR_CODE_SLOT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
        },
        func="async_clear_usercode",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_LOCK_USER,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required(ATTR_USER_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65534)
            ),
        },
        func="async_get_user",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_CREDENTIAL_STATUS,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required(ATTR_CREDENTIAL_TYPE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=8)
            ),
            vol.Required(ATTR_CREDENTIAL_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65534)
            ),
        },
        func="async_get_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
