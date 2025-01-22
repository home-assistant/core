"""HEOS integration coordinator.

Control of all HEOS devices is through connection to a single device. Data is pushed through events.
The coordinator is responsible for refreshing data in response to system-wide events and notifying
entities to update. Entities subscribe to entity-specific updates within the entity class itself.
"""

import logging

from pyheos import Credentials, Heos, HeosError, HeosOptions, MediaItem

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HeosCoordinator(DataUpdateCoordinator[None]):
    """Define the HEOS integration coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Set up the coordinator and set in config_entry."""
        self.host: str = config_entry.data[CONF_HOST]
        credentials: Credentials | None = None
        if config_entry.options:
            credentials = Credentials(
                config_entry.options[CONF_USERNAME], config_entry.options[CONF_PASSWORD]
            )
        # Setting all_progress_events=False ensures that we only receive a
        # media position update upon start of playback or when media changes
        self.heos = Heos(
            HeosOptions(
                self.host,
                all_progress_events=False,
                auto_reconnect=True,
                credentials=credentials,
            )
        )
        self.favorites: dict[int, MediaItem] = {}
        self.inputs: list[MediaItem] = []
        super().__init__(hass, _LOGGER, config_entry=config_entry, name=DOMAIN)

    async def async_setup(self) -> None:
        """Set up the coordinator; connect to the host; and retrieve initial data."""
        # Add before connect as it may occur during initial connection
        self.heos.add_on_user_credentials_invalid(self._async_on_auth_failure)
        # Connect to the device
        try:
            await self.heos.connect()
        except HeosError as error:
            raise ConfigEntryNotReady from error
        # Load players
        try:
            await self.heos.get_players()
        except HeosError as error:
            raise ConfigEntryNotReady from error

        if not self.heos.is_signed_in:
            _LOGGER.warning(
                "The HEOS System is not logged in: Enter credentials in the integration options to access favorites and streaming services"
            )
        # Retrieve initial data
        await self._async_update_sources()

    async def async_shutdown(self) -> None:
        """Disconnect all callbacks and disconnect from the device."""
        self.heos.dispatcher.disconnect_all()  # Removes all connected through heos.add_on_* and player.add_on_*
        await self.heos.disconnect()
        await super().async_shutdown()

    async def _async_on_auth_failure(self) -> None:
        """Handle when the user credentials are no longer valid."""
        assert self.config_entry is not None
        self.config_entry.async_start_reauth(self.hass)

    async def _async_update_sources(self) -> None:
        """Build source list for entities."""
        # Get favorites only if reportedly signed in.
        if self.heos.is_signed_in:
            try:
                self.favorites = await self.heos.get_favorites()
            except HeosError as error:
                _LOGGER.error("Unable to retrieve favorites: %s", error)
        # Get input sources (across all devices in the HEOS system)
        try:
            self.inputs = await self.heos.get_input_sources()
        except HeosError as error:
            _LOGGER.error("Unable to retrieve input sources: %s", error)
