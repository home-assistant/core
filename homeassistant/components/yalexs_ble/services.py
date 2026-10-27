"""Services for Yale Access Bluetooth locks."""

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    CREDENTIAL_TYPE_PIN,
    DOMAIN,
    MAX_PIN_SLOT,
    MIN_PIN_SLOT,
    YaleXSBLEService,
    YaleXSBLEServiceArgument,
)

_CREDENTIAL_TYPE = probatio.Required(YaleXSBLEServiceArgument.CREDENTIAL_TYPE)
_CREDENTIAL_INDEX = probatio.Required(YaleXSBLEServiceArgument.CREDENTIAL_INDEX)


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
        YaleXSBLEService.SET_LOCK_CREDENTIAL,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            _CREDENTIAL_TYPE: probatio.In([CREDENTIAL_TYPE_PIN]),
            probatio.Required(YaleXSBLEServiceArgument.CREDENTIAL_DATA): cv.string,
            _CREDENTIAL_INDEX: _slot(),
            probatio.Optional(YaleXSBLEServiceArgument.NAME): cv.string,
        },
        func="async_set_lock_credential",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YaleXSBLEService.CLEAR_LOCK_CREDENTIAL,
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
        YaleXSBLEService.GET_LOCK_CREDENTIAL_STATUS,
        admin_only=True,
        entity_domain=LOCK_DOMAIN,
        schema={
            _CREDENTIAL_TYPE: probatio.In([CREDENTIAL_TYPE_PIN]),
            _CREDENTIAL_INDEX: _slot(),
        },
        func="async_get_lock_credential_status",
        supports_response=SupportsResponse.ONLY,
    )
