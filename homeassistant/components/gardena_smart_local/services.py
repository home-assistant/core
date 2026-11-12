"""Services for the GARDENA smart local integration."""

import probatio

from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "open_valve",
        entity_domain=VALVE_DOMAIN,
        schema={
            probatio.Optional("duration"): probatio.All(
                probatio.Coerce(int), probatio.Range(min=60, max=10800)
            )
        },
        func="async_open_valve_for",
    )
