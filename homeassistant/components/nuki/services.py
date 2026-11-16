"""Services for the Nuki Bridge integration."""

from enum import StrEnum

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class NukiService(StrEnum):
    """Store keys for Nuki services."""

    LOCK_N_GO = "lock_n_go"
    SET_CONTINUOUS_MODE = "set_continuous_mode"


class NukiServiceArgument(StrEnum):
    """Store keys for Nuki service arguments."""

    UNLATCH = "unlatch"
    ENABLE = "enable"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Nuki Bridge integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NukiService.LOCK_N_GO,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Optional(NukiServiceArgument.UNLATCH, default=False): cv.boolean
        },
        func="lock_n_go",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NukiService.SET_CONTINUOUS_MODE,
        entity_domain=LOCK_DOMAIN,
        schema={probatio.Required(NukiServiceArgument.ENABLE): cv.boolean},
        func="set_continuous_mode",
    )
