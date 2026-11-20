"""Services for Matter devices."""

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    DOMAIN,
    SERVICE_CREDENTIAL_TYPES,
    USER_TYPE_REVERSE_MAP,
    MatterService,
    MatterServiceArgument,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Matter services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.WATER_HEATER_BOOST,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            # duration >=1
            probatio.Required(MatterServiceArgument.DURATION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(MatterServiceArgument.EMERGENCY_BOOST): cv.boolean,
            probatio.Optional(MatterServiceArgument.TEMPORARY_SETPOINT): probatio.All(
                probatio.Coerce(int), probatio.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
    )

    # Lock services - Full user CRUD
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.SET_LOCK_USER,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Optional(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(MatterServiceArgument.USER_NAME): probatio.Any(str, None),
            probatio.Optional(MatterServiceArgument.USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Optional(MatterServiceArgument.CREDENTIAL_RULE): probatio.In(
                CREDENTIAL_RULE_REVERSE_MAP.keys()
            ),
        },
        func="async_set_lock_user",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.CLEAR_LOCK_USER,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Any(probatio.Range(min=1), CLEAR_ALL_INDEX),
            ),
        },
        func="async_clear_lock_user",
    )

    # Lock services - Query operations
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.GET_LOCK_INFO,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_info",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.GET_LOCK_USERS,
        entity_domain=LOCK_DOMAIN,
        schema={},
        func="async_get_lock_users",
        supports_response=SupportsResponse.ONLY,
    )

    # Lock services - Credential management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.SET_LOCK_CREDENTIAL,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.CREDENTIAL_TYPE): probatio.In(
                SERVICE_CREDENTIAL_TYPES
            ),
            probatio.Required(MatterServiceArgument.CREDENTIAL_DATA): cv.string,
            probatio.Optional(MatterServiceArgument.CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
            probatio.Optional(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(MatterServiceArgument.USER_STATUS): probatio.In(
                ["occupied_enabled", "occupied_disabled"]
            ),
            probatio.Optional(MatterServiceArgument.USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
        },
        func="async_set_lock_credential",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.CLEAR_LOCK_CREDENTIAL,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.CREDENTIAL_TYPE): probatio.In(
                SERVICE_CREDENTIAL_TYPES
            ),
            probatio.Required(MatterServiceArgument.CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
        },
        func="async_clear_lock_credential",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MatterService.GET_LOCK_CREDENTIAL_STATUS,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(MatterServiceArgument.CREDENTIAL_TYPE): probatio.In(
                CREDENTIAL_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Required(MatterServiceArgument.CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
        },
        func="async_get_lock_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
