"""Services for the Fastdotcom integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, SERVICE_NAME
from .coordinator import FastdotcomDataUpdateCoordindator


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the service for the Fastdotcom integration."""

    @callback
    def collect_coordinator() -> FastdotcomDataUpdateCoordindator:
        """Collect the coordinator Fastdotcom."""
        config_entries = hass.config_entries.async_entries(DOMAIN)
        if not config_entries:
            raise HomeAssistantError("No Fast.com config entries found")

        for config_entry in config_entries:
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(f"{config_entry.title} is not loaded")
            coordinator: FastdotcomDataUpdateCoordindator = hass.data[DOMAIN][
                config_entry.entry_id
            ]
            break
        return coordinator

    async def async_perform_service(call: ServiceCall) -> None:
        """Perform a service call to manually run Fastdotcom."""
        ir.async_create_issue(
            hass,
            DOMAIN,
            "service_deprecation",
            breaks_in_ha_version="2024.7.0",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="service_deprecation",
        )
        coordinator = collect_coordinator()
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAME,
        async_perform_service,
    )
