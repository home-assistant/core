"""Services for the Motionblinds integration."""

import probatio

from homeassistant.components.cover import ATTR_TILT_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_ABSOLUTE_POSITION,
    ATTR_WIDTH,
    DOMAIN,
    SERVICE_SET_ABSOLUTE_POSITION,
)

SET_ABSOLUTE_POSITION_SCHEMA: VolDictType = {
    probatio.Required(ATTR_ABSOLUTE_POSITION): probatio.All(
        cv.positive_int, probatio.Range(max=100)
    ),
    probatio.Optional(ATTR_TILT_POSITION): probatio.All(
        cv.positive_int, probatio.Range(max=100)
    ),
    probatio.Optional(ATTR_WIDTH): probatio.All(
        cv.positive_int, probatio.Range(max=100)
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Motionblinds integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_ABSOLUTE_POSITION,
        entity_domain=COVER_DOMAIN,
        schema=SET_ABSOLUTE_POSITION_SCHEMA,
        func="async_set_absolute_position",
    )
