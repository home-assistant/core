"""Services for the Nuki Bridge integration."""

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_ENABLE, ATTR_UNLATCH, DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Nuki Bridge integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "lock_n_go",
        entity_domain=LOCK_DOMAIN,
        schema={probatio.Optional(ATTR_UNLATCH, default=False): cv.boolean},
        func="lock_n_go",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_continuous_mode",
        entity_domain=LOCK_DOMAIN,
        schema={probatio.Required(ATTR_ENABLE): cv.boolean},
        func="set_continuous_mode",
    )
