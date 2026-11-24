"""Services for Matter devices."""

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_DAYS,
    ATTR_END_DATE_TIME,
    ATTR_END_TIME,
    ATTR_HOLIDAY_INDEX,
    ATTR_OPERATING_MODE,
    ATTR_START_DATE_TIME,
    ATTR_START_TIME,
    ATTR_WEEK_DAY_INDEX,
    ATTR_YEAR_DAY_INDEX,
    CLEAR_ALL_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    DOMAIN,
    OPERATING_MODE_REVERSE_MAP,
    SCHEDULE_CLEAR_ALL_INDEX,
    SERVICE_CREDENTIAL_TYPES,
    USER_TYPE_REVERSE_MAP,
    WEEKDAY_MAP,
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

    # Lock services - Week day schedule management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_week_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_WEEK_DAY_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=253)
            ),
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=254)
            ),
            probatio.Required(ATTR_DAYS): probatio.All(
                probatio.EnsureList(),
                [probatio.In(WEEKDAY_MAP)],
                probatio.Length(min=1),
            ),
            probatio.Required(ATTR_START_TIME): cv.time,
            probatio.Required(ATTR_END_TIME): cv.time,
        },
        func="async_set_week_day_schedule",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_week_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_WEEK_DAY_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=253)
            ),
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=254)
            ),
        },
        func="async_get_week_day_schedule",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "clear_week_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_WEEK_DAY_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Range(min=1, max=SCHEDULE_CLEAR_ALL_INDEX),
            ),
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Any(probatio.Range(min=1, max=254), CLEAR_ALL_INDEX),
            ),
        },
        func="async_clear_week_day_schedule",
    )

    # Lock services - Year day schedule management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_year_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_YEAR_DAY_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=253)
            ),
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=254)
            ),
            probatio.Required(ATTR_START_DATE_TIME): cv.datetime,
            probatio.Required(ATTR_END_DATE_TIME): cv.datetime,
        },
        func="async_set_year_day_schedule",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_year_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_YEAR_DAY_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=253)
            ),
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=254)
            ),
        },
        func="async_get_year_day_schedule",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "clear_year_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_YEAR_DAY_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Range(min=1, max=SCHEDULE_CLEAR_ALL_INDEX),
            ),
            probatio.Required(MatterServiceArgument.USER_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Any(probatio.Range(min=1, max=254), CLEAR_ALL_INDEX),
            ),
        },
        func="async_clear_year_day_schedule",
    )

    # Lock services - Holiday schedule management (lock-wide, no user_index)
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_holiday_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_HOLIDAY_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=253)
            ),
            probatio.Required(ATTR_START_DATE_TIME): cv.datetime,
            probatio.Required(ATTR_END_DATE_TIME): cv.datetime,
            probatio.Required(ATTR_OPERATING_MODE): probatio.In(
                OPERATING_MODE_REVERSE_MAP.keys()
            ),
        },
        func="async_set_holiday_schedule",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_holiday_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_HOLIDAY_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=253)
            ),
        },
        func="async_get_holiday_schedule",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "clear_holiday_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(ATTR_HOLIDAY_INDEX): probatio.All(
                probatio.Coerce(int),
                probatio.Range(min=1, max=SCHEDULE_CLEAR_ALL_INDEX),
            ),
        },
        func="async_clear_holiday_schedule",
    )
