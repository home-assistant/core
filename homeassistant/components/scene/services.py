"""Services for the Scene integration."""

import probatio

from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.const import SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback

from .const import DATA_COMPONENT


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the scene services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_TURN_ON,
        {
            ATTR_TRANSITION: probatio.All(
                probatio.Coerce(float), probatio.Clamp(min=0, max=6553)
            )
        },
        "_async_activate",
    )
