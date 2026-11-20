"""Services for the Overkiz integration."""

import probatio

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, OverkizService, OverkizServiceArgument

POSITION_MIN = 0
POSITION_MAX = 100


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Overkiz integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OverkizService.SET_COVER_POSITION_AND_TILT,
        entity_domain=COVER_DOMAIN,
        schema={
            probatio.Required(OverkizServiceArgument.POSITION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=POSITION_MIN, max=POSITION_MAX)
            ),
            probatio.Required(OverkizServiceArgument.TILT_POSITION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=POSITION_MIN, max=POSITION_MAX)
            ),
        },
        func="async_set_cover_position_and_tilt",
        required_features=[
            CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION
        ],
    )
