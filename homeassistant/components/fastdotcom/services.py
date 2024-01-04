"""Services for the Fastdotcom integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SERVICE_NAME
from .coordinator import FastdotcomDataUpdateCoordindator


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the service for the Fastdotcom integration."""

    @callback
    def collect_coordinator() -> FastdotcomDataUpdateCoordindator:
        config_entries = list[ConfigEntry]()
        for config_entry in config_entries:
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(f"{config_entry.title} is not loaded")
            coordinator: FastdotcomDataUpdateCoordindator = hass.data[DOMAIN][
                config_entry.entry_id
            ]
            break
        return coordinator

    async def async_perform_service(call: ServiceCall) -> None:
        """Perform a service on the device."""
        coordinator = collect_coordinator()
        await coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAME,
        async_perform_service,
    )
