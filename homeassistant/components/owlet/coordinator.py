"""Owlet integration coordinator class."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyowletapi.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletError,
)
from pyowletapi.sock import Sock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)


class OwletCoordinator(DataUpdateCoordinator[None]):
    """Coordinator is responsible for querying the device at a specified route."""

    def __init__(self, hass: HomeAssistant, sock: Sock, entry: ConfigEntry) -> None:
        """Initialise a custom coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLLING_INTERVAL),
        )
        self.sock = sock
        self.config_entry: ConfigEntry = entry

    async def _async_update_data(self) -> None:
        """Fetch the data from the device."""
        try:
            properties = await self.sock.update_properties()
            if properties["tokens"]:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, **properties["tokens"]},
                )
        except OwletAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed for {self.config_entry.data[CONF_EMAIL]}"
            ) from err
        except (OwletError, OwletConnectionError) as err:
            raise UpdateFailed(err) from err
