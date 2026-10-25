"""Services for Matter devices."""

from typing import Any

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import ATTR_NAME
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
    CAMERA_ZONE_SETTABLE_USES,
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

ATTR_COLOR = "color"
ATTR_USE = "use"
ATTR_VERTICES = "vertices"
ATTR_ZONE_ID = "zone_id"

ZONE_ID = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=65535))
ZONE_PERCENT = probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=100))
# Matter limits zone names to 32 bytes.
ZONE_NAME_MAX_BYTES = 32


def _zone_name(value: Any) -> str:
    """Validate a zone name."""
    name = cv.string(value)
    if not name.strip():
        raise probatio.Invalid("Zone name can't be empty")
    if len(name.encode()) > ZONE_NAME_MAX_BYTES:
        raise probatio.Invalid(
            f"Zone name can't be longer than {ZONE_NAME_MAX_BYTES} bytes"
        )
    return name


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
            probatio.Required(ATTR_DURATION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(ATTR_EMERGENCY_BOOST): cv.boolean,
            probatio.Optional(ATTR_TEMPORARY_SETPOINT): probatio.All(
                probatio.Coerce(int), probatio.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_camera_zones",
        entity_domain=CAMERA_DOMAIN,
        schema={},
        func="async_get_camera_zones",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_camera_zone",
        admin_only=True,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Optional(ATTR_ZONE_ID): ZONE_ID,
            probatio.Required(ATTR_NAME): _zone_name,
            probatio.Required(ATTR_USE): probatio.In(CAMERA_ZONE_SETTABLE_USES),
            probatio.Required(ATTR_VERTICES): probatio.All(
                probatio.EnsureList(),
                [
                    {
                        probatio.Required("x"): ZONE_PERCENT,
                        probatio.Required("y"): ZONE_PERCENT,
                    }
                ],
                probatio.Length(min=3, max=12),
            ),
            probatio.Optional(ATTR_COLOR): probatio.Match(
                r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?\Z"
            ),
        },
        func="async_set_camera_zone",
        supports_response=SupportsResponse.OPTIONAL,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "clear_camera_zone",
        admin_only=True,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(ATTR_ZONE_ID): ZONE_ID},
        func="async_clear_camera_zone",
    )

    # Lock services - Full user CRUD
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_lock_user",
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Optional(ATTR_USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(ATTR_USER_NAME): probatio.Any(str, None),
            probatio.Optional(ATTR_USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Optional(ATTR_CREDENTIAL_RULE): probatio.In(
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
            probatio.Required(ATTR_USER_INDEX): probatio.All(
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
            probatio.Required(ATTR_CREDENTIAL_TYPE): probatio.In(
                SERVICE_CREDENTIAL_TYPES
            ),
            probatio.Required(ATTR_CREDENTIAL_DATA): cv.string,
            probatio.Optional(ATTR_CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
            probatio.Optional(ATTR_USER_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            ),
            probatio.Optional(ATTR_USER_STATUS): probatio.In(
                ["occupied_enabled", "occupied_disabled"]
            ),
            probatio.Optional(ATTR_USER_TYPE): probatio.In(
                USER_TYPE_REVERSE_MAP.keys()
            ),
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
            probatio.Required(ATTR_CREDENTIAL_TYPE): probatio.In(
                SERVICE_CREDENTIAL_TYPES
            ),
            probatio.Required(ATTR_CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
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
            probatio.Required(ATTR_CREDENTIAL_TYPE): probatio.In(
                CREDENTIAL_TYPE_REVERSE_MAP.keys()
            ),
            probatio.Required(ATTR_CREDENTIAL_INDEX): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0)
            ),
        },
        func="async_get_lock_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
