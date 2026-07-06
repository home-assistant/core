"""Services for the Overkiz integration."""

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN

SERVICE_SET_COVER_POSITION_AND_TILT = "set_cover_position_and_tilt"

POSITION_MIN = 0
POSITION_MAX = 100


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Overkiz integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_COVER_POSITION_AND_TILT,
        entity_domain=COVER_DOMAIN,
        schema={
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=POSITION_MIN, max=POSITION_MAX)
            ),
            vol.Required(ATTR_TILT_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=POSITION_MIN, max=POSITION_MAX)
            ),
        },
        func="async_set_cover_position_and_tilt",
        required_features=[
            CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION
        ],
    )
