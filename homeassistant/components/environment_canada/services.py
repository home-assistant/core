"""Define services for the Environment Canada integration."""

from typing import Any

from env_canada import ECWeather
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_GET_ALERTS = "get_alerts"
SERVICE_GET_ALERTS_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})


async def _async_get_alerts(call: ServiceCall) -> dict[str, Any]:
    """Clear text in the keyboard input field on an Apple TV."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    ec: ECWeather | None = entry.runtime_data.weather_coordinator.ec_data
    if ec is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_connected",
        )
    return ec.alerts


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Apple TV integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ALERTS,
        _async_get_alerts,
        schema=SERVICE_GET_ALERTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
