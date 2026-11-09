"""Services for the National Weather Service (NWS) integration."""

import probatio

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the National Weather Service (NWS) integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_forecasts_extra",
        entity_domain=WEATHER_DOMAIN,
        schema={probatio.Required("type"): probatio.In(("hourly", "twice_daily"))},
        func="async_get_forecasts_extra_service",
        supports_response=SupportsResponse.ONLY,
    )
