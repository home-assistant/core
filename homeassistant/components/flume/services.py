"""Services for flume."""

from enum import StrEnum

import probatio

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


class FlumeService(StrEnum):
    """Store keys for Flume services."""

    LIST_NOTIFICATIONS = "list_notifications"


class FlumeServiceArgument(StrEnum):
    """Store keys for Flume service arguments."""

    CONFIG_ENTRY = "config_entry"


LIST_NOTIFICATIONS_SERVICE_SCHEMA = probatio.All(
    {
        probatio.Required(FlumeServiceArgument.CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    },
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    @callback
    def list_notifications(call: ServiceCall) -> ServiceResponse:
        """Return the user notifications."""
        entry_id: str = call.data[FlumeServiceArgument.CONFIG_ENTRY]
        entry: FlumeConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, entry_id
        )
        return {
            "notifications": entry.runtime_data.notifications_coordinator.notifications  # type: ignore[dict-item]
        }

    hass.services.async_register(
        DOMAIN,
        FlumeService.LIST_NOTIFICATIONS,
        list_notifications,
        schema=LIST_NOTIFICATIONS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
