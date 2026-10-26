"""Services for the Schlage integration."""

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SERVICE_ADD_CODE, SERVICE_DELETE_CODE, SERVICE_GET_CODES


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Schlage integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_CODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required("name"): cv.string,
            probatio.Required("code"): probatio.All(
                cv.string, cv.matches_regex(r"^\d{4,8}$")
            ),
            probatio.Optional("notify_on_use", default=True): cv.boolean,
        },
        func=SERVICE_ADD_CODE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_CODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required("name"): cv.string,
        },
        func=SERVICE_DELETE_CODE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_CODES,
        entity_domain=LOCK_DOMAIN,
        schema=None,
        func=SERVICE_GET_CODES,
        supports_response=SupportsResponse.ONLY,
    )
