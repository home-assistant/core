"""Neato services."""

from enum import StrEnum

import probatio

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class NeatoService(StrEnum):
    """Store keys for Neato services."""

    CUSTOM_CLEANING = "custom_cleaning"


class NeatoServiceArgument(StrEnum):
    """Store keys for Neato service arguments."""

    MODE = "mode"
    NAVIGATION = "navigation"
    CATEGORY = "category"
    ZONE = "zone"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NeatoService.CUSTOM_CLEANING,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Optional(NeatoServiceArgument.MODE, default=2): cv.positive_int,
            probatio.Optional(
                NeatoServiceArgument.NAVIGATION, default=1
            ): cv.positive_int,
            probatio.Optional(
                NeatoServiceArgument.CATEGORY, default=4
            ): cv.positive_int,
            probatio.Optional(NeatoServiceArgument.ZONE): cv.string,
        },
        func="neato_custom_cleaning",
    )
