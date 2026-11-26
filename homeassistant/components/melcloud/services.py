"""Services for the MELCloud integration."""

from enum import StrEnum

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class MelCloudService(StrEnum):
    """Store keys for MELCloud services."""

    SET_VANE_HORIZONTAL = "set_vane_horizontal"
    SET_VANE_VERTICAL = "set_vane_vertical"


class MelCloudServiceArgument(StrEnum):
    """Store keys for MELCloud service arguments."""

    POSITION = "position"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the MELCloud integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MelCloudService.SET_VANE_HORIZONTAL,
        entity_domain=CLIMATE_DOMAIN,
        schema={probatio.Required(MelCloudServiceArgument.POSITION): cv.string},
        func="async_set_vane_horizontal",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MelCloudService.SET_VANE_VERTICAL,
        entity_domain=CLIMATE_DOMAIN,
        schema={probatio.Required(MelCloudServiceArgument.POSITION): cv.string},
        func="async_set_vane_vertical",
    )
