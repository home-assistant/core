"""Services for the Subaru integration."""

import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import ATTR_DOOR, DOMAIN, SERVICE_UNLOCK_SPECIFIC_DOOR, UNLOCK_VALID_DOORS


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Subaru services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UNLOCK_SPECIFIC_DOOR,
        entity_domain=LOCK_DOMAIN,
        schema={vol.Required(ATTR_DOOR): vol.In(UNLOCK_VALID_DOORS)},
        func="async_unlock_specific_door",
    )
