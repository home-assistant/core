"""Services for WMS WebControl pro."""

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_MOVE_COVER


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for WMS WebControl pro."""
    service.async_register_platform_entity_service(
        hass,
        service_domain=DOMAIN,
        service_name=SERVICE_MOVE_COVER,
        entity_domain=COVER_DOMAIN,
        func=f"async_service_{SERVICE_MOVE_COVER}",
        schema={
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required(ATTR_TILT_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=-127, max=127)
            ),
        },
    )
