"""Services for the Schlage integration."""

from enum import StrEnum

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class SchlageService(StrEnum):
    """Store keys for Schlage services."""

    GET_CODES = "get_codes"
    ADD_CODE = "add_code"
    DELETE_CODE = "delete_code"


class SchlageServiceArgument(StrEnum):
    """Store keys for Schlage service arguments."""

    NAME = "name"
    CODE = "code"
    NOTIFY_ON_USE = "notify_on_use"
    START_DATETIME = "start_datetime"
    END_DATETIME = "end_datetime"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Schlage integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SchlageService.ADD_CODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(SchlageServiceArgument.NAME): cv.string,
            probatio.Required(SchlageServiceArgument.CODE): probatio.All(
                cv.string, cv.matches_regex(r"^\d{4,8}$")
            ),
            probatio.Optional(
                SchlageServiceArgument.NOTIFY_ON_USE, default=True
            ): cv.boolean,
            probatio.Optional(SchlageServiceArgument.START_DATETIME): cv.datetime,
            probatio.Optional(SchlageServiceArgument.END_DATETIME): cv.datetime,
        },
        func="add_code",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SchlageService.DELETE_CODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(SchlageServiceArgument.NAME): cv.string,
        },
        func="delete_code",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SchlageService.GET_CODES,
        entity_domain=LOCK_DOMAIN,
        schema=None,
        func="get_codes",
        supports_response=SupportsResponse.ONLY,
    )
