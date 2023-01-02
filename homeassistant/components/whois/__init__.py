"""The Whois integration."""
from __future__ import annotations

from whois import Domain, query as whois_query
from whois.exceptions import (
    FailedParsingWhoisOutput,
    UnknownDateFormat,
    UnknownTld,
    WhoisCommandFailed,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, PLATFORMS, SCAN_INTERVAL


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    async def _async_query_domain() -> Domain | None:
        """Query WHOIS for domain information."""
        try:
            return await hass.async_add_executor_job(
                whois_query, entry.data[CONF_DOMAIN]
            )
        except UnknownTld as ex:
            raise UpdateFailed("Could not set up whois, TLD is unknown") from ex
        except (FailedParsingWhoisOutput, WhoisCommandFailed, UnknownDateFormat) as ex:
            raise UpdateFailed("An error occurred during WHOIS lookup") from ex

    coordinator: DataUpdateCoordinator[Domain | None] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_APK",
        update_interval=SCAN_INTERVAL,
        update_method=_async_query_domain,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
