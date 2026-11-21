"""Services for the Met Office integration."""

import voluptuous as vol

from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LATITUDE,
    ATTR_LOCATION,
    ATTR_LONGITUDE,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, selector, service

from .const import DOMAIN, SERVICE_SET_FORECAST_LOCATION
from .coordinator import MetOfficeConfigEntry

SET_FORECAST_LOCATION_SCHEMA = vol.Schema(
    vol.Schema(
        {
            vol.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
                {
                    "integration": DOMAIN,
                }
            ),
            vol.Inclusive(ATTR_LATITUDE, ATTR_LOCATION): cv.latitude,
            vol.Inclusive(ATTR_LONGITUDE, ATTR_LOCATION): cv.longitude,
        }
    ),
)


async def set_forecast_location(call: ServiceCall) -> None:
    """Set location of forecast from service call."""
    entry: MetOfficeConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    await entry.runtime_data.update_coordinates(
        call.data.get(ATTR_LATITUDE), call.data.get(ATTR_LONGITUDE)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Metoffice services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FORECAST_LOCATION,
        set_forecast_location,
        schema=SET_FORECAST_LOCATION_SCHEMA,
    )
