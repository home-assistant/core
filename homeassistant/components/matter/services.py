"""Services for Matter devices."""

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
    ATTR_DAYS,
    ATTR_END_HOUR,
    ATTR_END_MINUTE,
    ATTR_END_TIME,
    ATTR_HOLIDAY_INDEX,
    ATTR_OPERATING_MODE,
    ATTR_START_HOUR,
    ATTR_START_MINUTE,
    ATTR_START_TIME,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    ATTR_WEEK_DAY_INDEX,
    ATTR_YEAR_DAY_INDEX,
    CLEAR_ALL_INDEX,
    CLEAR_ALL_SCHEDULE_INDEX,
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    DAY_OF_WEEK_MAP,
    DOMAIN,
    OPERATING_MODE_REVERSE_MAP,
    SERVICE_CREDENTIAL_TYPES,
    USER_TYPE_REVERSE_MAP,
)

# A schedule index (week day / year day / holiday) is 1-based, or the
# CLEAR_ALL_SCHEDULE_INDEX sentinel when clearing all schedules of that type.
_SCHEDULE_INDEX_SCHEMA = vol.All(
    vol.Coerce(int),
    vol.Any(
        vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1), CLEAR_ALL_SCHEDULE_INDEX
    ),
)
# A user index for a schedule command is 1-based, or CLEAR_ALL_INDEX to target
# all users at once (only meaningful for Clear*Schedule commands).
_SCHEDULE_USER_INDEX_SCHEMA = vol.All(
    vol.Coerce(int), vol.Any(vol.Range(min=1), CLEAR_ALL_INDEX)
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

    # Lock services - Week day schedule management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_week_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_WEEK_DAY_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1)
            ),
            vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(ATTR_DAYS): [vol.In(DAY_OF_WEEK_MAP.keys())],
            vol.Required(ATTR_START_HOUR): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Required(ATTR_START_MINUTE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=59)
            ),
            vol.Required(ATTR_END_HOUR): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=23)
            ),
            vol.Required(ATTR_END_MINUTE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=59)
            ),
        },
        func="async_set_week_day_schedule",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_week_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_WEEK_DAY_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1)
            ),
            vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
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
            vol.Required(ATTR_WEEK_DAY_INDEX): _SCHEDULE_INDEX_SCHEMA,
            vol.Required(ATTR_USER_INDEX): _SCHEDULE_USER_INDEX_SCHEMA,
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
            vol.Required(ATTR_YEAR_DAY_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1)
            ),
            vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(ATTR_START_TIME): cv.datetime,
            vol.Required(ATTR_END_TIME): cv.datetime,
        },
        func="async_set_year_day_schedule",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_year_day_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_YEAR_DAY_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1)
            ),
            vol.Required(ATTR_USER_INDEX): vol.All(vol.Coerce(int), vol.Range(min=1)),
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
            vol.Required(ATTR_YEAR_DAY_INDEX): _SCHEDULE_INDEX_SCHEMA,
            vol.Required(ATTR_USER_INDEX): _SCHEDULE_USER_INDEX_SCHEMA,
        },
        func="async_clear_year_day_schedule",
    )

    # Lock services - Holiday schedule management
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_holiday_schedule",
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required(ATTR_HOLIDAY_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1)
            ),
            vol.Required(ATTR_START_TIME): cv.datetime,
            vol.Required(ATTR_END_TIME): cv.datetime,
            vol.Required(ATTR_OPERATING_MODE): vol.In(
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
            vol.Required(ATTR_HOLIDAY_INDEX): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=CLEAR_ALL_SCHEDULE_INDEX - 1)
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
            vol.Required(ATTR_HOLIDAY_INDEX): _SCHEDULE_INDEX_SCHEMA,
        },
        func="async_clear_holiday_schedule",
    )
