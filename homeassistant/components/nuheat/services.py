"""Register NuHeat thermostat actions."""

import probatio

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register actions once across NuHeat account entries."""
    if not hass.services.has_service(DOMAIN, "set_temporary_hold"):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            "set_temporary_hold",
            entity_domain="climate",
            schema={
                probatio.Required(ATTR_TEMPERATURE): probatio.Coerce(float),
                probatio.Required("hold_until"): cv.datetime,
            },
            func="async_set_temporary_hold",
        )
