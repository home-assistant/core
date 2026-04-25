"""Services for Matter devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_CREDENTIAL_DATA,
    ATTR_CREDENTIAL_INDEX,
    ATTR_CREDENTIAL_RULE,
    ATTR_CREDENTIAL_TYPE,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    DOMAIN,
    SERVICE_CREDENTIAL_TYPES,
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

    # Lock services - Full user CRUD
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_lock_user",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Optional(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(ATTR_USER_NAME): vol.Any(str, None),
            vol.Optional(ATTR_USER_TYPE): vol.In(USER_TYPE_REVERSE_MAP.keys()),
            vol.Optional(ATTR_CREDENTIAL_RULE): vol.In(
                CREDENTIAL_RULE_REVERSE_MAP.keys()
            ),
        },
        func="async_set_lock_user",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "clear_lock_user",
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
        "get_lock_info",
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_info",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_lock_users",
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_users",
        supports_response=SupportsResponse.ONLY,
    )

    # Lock services - Credential management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_lock_credential",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_CREDENTIAL_TYPE): vol.In(SERVICE_CREDENTIAL_TYPES),
            vol.Required(ATTR_CREDENTIAL_DATA): str,
            vol.Optional(ATTR_CREDENTIAL_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            vol.Optional(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(ATTR_USER_STATUS): vol.In(
                ["occupied_enabled", "occupied_disabled"]
            ),
            vol.Optional(ATTR_USER_TYPE): vol.In(USER_TYPE_REVERSE_MAP.keys()),
        },
        func="async_set_lock_credential",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "clear_lock_credential",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_CREDENTIAL_TYPE): vol.In(SERVICE_CREDENTIAL_TYPES),
            vol.Required(ATTR_CREDENTIAL_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
        },
        func="async_clear_lock_credential",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_lock_credential_status",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_CREDENTIAL_TYPE): vol.In(
                CREDENTIAL_TYPE_REVERSE_MAP.keys()
            ),
            vol.Required(ATTR_CREDENTIAL_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
        },
        func="async_get_lock_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
