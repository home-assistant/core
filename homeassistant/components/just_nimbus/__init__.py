"""The Just Nimbus integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import justnimbus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


class JustNimbusError(HomeAssistantError):
    """Base exception of the Just Nimbus integration."""


class InvalidClientId(JustNimbusError):
    """Exception to be raised by Just Nimbus when the client id provided is invalid."""


class CannotConnect(JustNimbusError):
    """Error to indicate we cannot connect."""


class UnknownError(JustNimbusError):
    """Exception to be raised by Just Nimbus when an unknown error has occurred."""


class JustNimbusCoordinator(DataUpdateCoordinator[justnimbus.JustNimbusModel]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=entry.data[CONF_SCAN_INTERVAL]),
        )
        self._entry = entry

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> justnimbus.JustNimbusModel:
        """Fetch the latest data from the source."""
        return await self.hass.async_add_executor_job(
            get_data, self.hass, self._entry.data
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CO2 Signal from a config entry."""
    coordinator = JustNimbusCoordinator(hass=hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def get_data(hass: HomeAssistant, config: dict) -> justnimbus.JustNimbusModel:
    """Get data from the API."""
    return justnimbus.JustNimbusClient(client_id=config[CONF_CLIENT_ID]).get_data()
