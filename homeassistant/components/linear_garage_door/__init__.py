"""The Linear Garage Door integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .coordinator import LinearConfigEntry, LinearUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.COVER, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: LinearConfigEntry) -> bool:
    """Set up Linear Garage Door from a config entry."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        breaks_in_ha_version="2025.8.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_integration",
        translation_placeholders={
            "nice_go": "https://www.home-assistant.io/integrations/linear_garage_door",
            "entries": "/config/integrations/integration/linear_garage_door",
        },
    )

    coordinator = LinearUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinearConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: LinearConfigEntry) -> None:
    """Remove a config entry."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        ir.async_delete_issue(hass, DOMAIN, DOMAIN)
        # Remove any remaining disabled or ignored entries
        for _entry in hass.config_entries.async_entries(DOMAIN):
            hass.async_create_task(hass.config_entries.async_remove(_entry.entry_id))
