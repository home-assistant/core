"""Services for flume."""

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import service
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN
from .coordinator import FlumeConfigEntry

SERVICE_LIST_NOTIFICATIONS = "list_notifications"
CONF_CONFIG_ENTRY = "config_entry"
LIST_NOTIFICATIONS_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
    },
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    @callback
    def list_notifications(call: ServiceCall) -> ServiceResponse:
        """Return the user notifications."""
        entry_id: str = call.data[CONF_CONFIG_ENTRY]
        entry: FlumeConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, entry_id
        )
        return {
            "notifications": entry.runtime_data.notifications_coordinator.notifications  # type: ignore[dict-item]
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_NOTIFICATIONS,
        list_notifications,
        schema=LIST_NOTIFICATIONS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
