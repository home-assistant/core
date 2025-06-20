"""The HERE Travel Time integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_MODE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, TRAVEL_MODE_PUBLIC
from .coordinator import (
    HereConfigEntry,
    HERERoutingDataUpdateCoordinator,
    HERETransitDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: HereConfigEntry) -> bool:
    """Set up HERE Travel Time from a config entry."""
    api_key = config_entry.data[CONF_API_KEY]

    alert_for_multiple_entries(hass)

    cls: type[HERETransitDataUpdateCoordinator | HERERoutingDataUpdateCoordinator]
    if config_entry.data[CONF_MODE] in {TRAVEL_MODE_PUBLIC, "publicTransportTimeTable"}:
        cls = HERETransitDataUpdateCoordinator
    else:
        cls = HERERoutingDataUpdateCoordinator

    data_coordinator = cls(hass, config_entry, api_key)
    config_entry.runtime_data = data_coordinator

    async def _async_update_at_start(_: HomeAssistant) -> None:
        await data_coordinator.async_refresh()

    config_entry.async_on_unload(async_at_started(hass, _async_update_at_start))
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


def alert_for_multiple_entries(hass: HomeAssistant) -> None:
    """Check if there are multiple entries for the same API key."""
    if len(hass.config_entries.async_entries(DOMAIN)) > 1:
        async_create_issue(
            hass,
            DOMAIN,
            "multiple_here_travel_time_entries",
            learn_more_url="https://github.com/home-assistant/home-assistant.io/pull/39653",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="multiple_here_travel_time_entries",
            translation_placeholders={
                "pricing_page": "https://www.here.com/get-started/pricing",
            },
        )


async def async_unload_entry(
    hass: HomeAssistant, config_entry: HereConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
