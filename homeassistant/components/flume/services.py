"""The flume integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
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
def _list_notifications(call: ServiceCall) -> ServiceResponse:
    """Return the user notifications."""
    entry_id: str = call.data[CONF_CONFIG_ENTRY]
    entry: FlumeConfigEntry | None = call.hass.config_entries.async_get_entry(entry_id)
    if not entry:
        raise ValueError(f"Invalid config entry: {entry_id}")
    if not entry.state == ConfigEntryState.LOADED:
        raise ValueError(f"Config entry not loaded: {entry_id}")
    return {
        "notifications": entry.runtime_data.notifications_coordinator.notifications  # type: ignore[dict-item]
    }


def async_setup_services(hass: HomeAssistant) -> None:
    """Add the services for the flume integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_NOTIFICATIONS,
        _list_notifications,
        schema=LIST_NOTIFICATIONS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
