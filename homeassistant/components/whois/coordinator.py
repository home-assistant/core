"""DataUpdateCoordinator for the Whois integration."""

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

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class WhoisCoordinator(DataUpdateCoordinator[Domain | None]):
    """Class to manage fetching WHOIS data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Domain | None:
        """Query WHOIS for domain information."""
        try:
            return await self.hass.async_add_executor_job(
                whois_query, self.config_entry.data[CONF_DOMAIN]
            )
        except UnknownTld as ex:
            raise UpdateFailed("Could not set up whois, TLD is unknown") from ex
        except (FailedParsingWhoisOutput, WhoisCommandFailed, UnknownDateFormat) as ex:
            raise UpdateFailed("An error occurred during WHOIS lookup") from ex
