"""Services for Yale Access Bluetooth locks."""

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_CREDENTIAL_DATA,
    ATTR_CREDENTIAL_INDEX,
    ATTR_CREDENTIAL_TYPE,
    CREDENTIAL_TYPE_PIN,
    DOMAIN,
    MAX_PIN_SLOT,
    MIN_PIN_SLOT,
)

SERVICE_SET_LOCK_CREDENTIAL = "set_lock_credential"
SERVICE_CLEAR_LOCK_CREDENTIAL = "clear_lock_credential"
SERVICE_GET_LOCK_CREDENTIAL_STATUS = "get_lock_credential_status"

_CREDENTIAL_TYPE = probatio.Required(ATTR_CREDENTIAL_TYPE)
_CREDENTIAL_INDEX = probatio.Required(ATTR_CREDENTIAL_INDEX)


def _slot() -> probatio.All:
    """Return a validator for a keypad PIN slot."""
    return probatio.All(
        probatio.Coerce(int), probatio.Range(min=MIN_PIN_SLOT, max=MAX_PIN_SLOT)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Yale Access Bluetooth services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LOCK_CREDENTIAL,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            _CREDENTIAL_TYPE: probatio.In([CREDENTIAL_TYPE_PIN]),
            probatio.Required(ATTR_CREDENTIAL_DATA): cv.string,
            _CREDENTIAL_INDEX: _slot(),
            probatio.Optional(ATTR_NAME): cv.string,
        },
        func="async_set_lock_credential",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_LOCK_CREDENTIAL,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            _CREDENTIAL_TYPE: probatio.In([CREDENTIAL_TYPE_PIN]),
            _CREDENTIAL_INDEX: _slot(),
        },
        func="async_clear_lock_credential",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_LOCK_CREDENTIAL_STATUS,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            _CREDENTIAL_TYPE: probatio.In([CREDENTIAL_TYPE_PIN]),
            _CREDENTIAL_INDEX: _slot(),
        },
        func="async_get_lock_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
