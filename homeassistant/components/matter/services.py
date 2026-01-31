"""Services for Matter devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_CODE_SLOT,
    ATTR_CREDENTIAL_RULE,
    ATTR_PIN_CODE,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_TYPE,
    ATTR_USERCODE,
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    DOMAIN,
    SERVICE_CLEAR_LOCK_USER,
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_GET_LOCK_INFO,
    SERVICE_GET_LOCK_USERS,
    SERVICE_SET_LOCK_USER,
    SERVICE_SET_LOCK_USERCODE,
    USER_TYPE_REVERSE_MAP,
)

ATTR_DURATION = "duration"
ATTR_EMERGENCY_BOOST = "emergency_boost"
ATTR_TEMPORARY_SETPOINT = "temporary_setpoint"

SERVICE_WATER_HEATER_BOOST = "water_heater_boost"


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

    # Lock services - Simple PIN operations
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LOCK_USERCODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_CODE_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(ATTR_USERCODE): cv.string,
        },
        func="async_set_lock_usercode",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_LOCK_USERCODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_CODE_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        },
        func="async_clear_lock_usercode",
    )

    # Lock services - Full user CRUD
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LOCK_USER,
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Optional(ATTR_USER_INDEX): vol.Any(
                vol.All(vol.Coerce(int), vol.Range(min=1)), None
            ),
            vol.Optional(ATTR_USER_NAME): vol.Any(str, None),
            vol.Optional(ATTR_USER_TYPE, default="unrestricted_user"): vol.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
            vol.Optional(ATTR_CREDENTIAL_RULE, default="single"): vol.In(
                CREDENTIAL_RULE_REVERSE_MAP.keys()
            ),
            vol.Optional(ATTR_PIN_CODE): vol.Any(str, None),
        },
        func="async_set_lock_user",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_LOCK_USER,
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_USER_INDEX): vol.All(
                vol.Coerce(int),
                vol.Any(vol.Range(min=1), CLEAR_ALL_INDEX),
            ),
        },
        func="async_clear_lock_user",
    )

    # Lock services - Query operations
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_LOCK_INFO,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_info",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_LOCK_USERS,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_users",
        supports_response=SupportsResponse.ONLY,
    )
