"""HEOS integration coordinator.

Control of all HEOS devices is through connection to a single device. Data is pushed through events.
The coordinator is responsible for refreshing data in response to system-wide events and notifying
entities to update. Entities subscribe to entity-specific updates within the entity class itself.
"""

import logging

from pyheos import (
    Credentials,
    Heos,
    HeosError,
    HeosOptions,
    MediaItem,
    PlayerUpdateResult,
    const,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
        # Attach event callbacks
        self.heos.add_on_disconnected(self._async_on_disconnected)
        self.heos.add_on_connected(self._async_on_reconnected)
        self.heos.add_on_controller_event(self._async_on_controller_event)

    async def async_shutdown(self) -> None:
        """Disconnect all callbacks and disconnect from the device."""
        self.heos.dispatcher.disconnect_all()  # Removes all connected through heos.add_on_* and player.add_on_*
        await self.heos.disconnect()
        await super().async_shutdown()

    async def _async_on_auth_failure(self) -> None:
        """Handle when the user credentials are no longer valid."""
        assert self.config_entry is not None
        self.config_entry.async_start_reauth(self.hass)

    async def _async_on_disconnected(self) -> None:
        """Handle when disconnected so entities are marked unavailable."""
        _LOGGER.warning("Connection to HEOS host %s lost", self.host)
        self.async_update_listeners()

    async def _async_on_reconnected(self) -> None:
        """Handle when reconnected so resources are updated and entities marked available."""
        await self._async_update_players()
        _LOGGER.warning("Successfully reconnected to HEOS host %s", self.host)
        self.async_update_listeners()

    async def _async_on_controller_event(
        self, event: str, data: PlayerUpdateResult | None
    ) -> None:
        """Handle a controller event, such as players or groups changed."""
        if event == const.EVENT_PLAYERS_CHANGED:
            assert data is not None
            if data.updated_player_ids:
                self._async_update_player_ids(data.updated_player_ids)
        self.async_update_listeners()

    def _async_update_player_ids(self, updated_player_ids: dict[int, int]) -> None:
        """Update the IDs in the device and entity registry."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        # updated_player_ids contains the mapped IDs in format old:new
        for old_id, new_id in updated_player_ids.items():
            # update device registry
            entry = device_registry.async_get_device(
                identifiers={(DOMAIN, str(old_id))}
            )
            if entry:
                new_identifiers = entry.identifiers.copy()
                new_identifiers.remove((DOMAIN, str(old_id)))
                new_identifiers.add((DOMAIN, str(new_id)))
                device_registry.async_update_device(
                    entry.id,
                    new_identifiers=new_identifiers,
                )
                _LOGGER.debug(
                    "Updated device %s identifiers to %s", entry.id, new_identifiers
                )
            # update entity registry
            entity_id = entity_registry.async_get_entity_id(
                Platform.MEDIA_PLAYER, DOMAIN, str(old_id)
            )
            if entity_id:
                entity_registry.async_update_entity(
                    entity_id, new_unique_id=str(new_id)
                )
                _LOGGER.debug("Updated entity %s unique id to %s", entity_id, new_id)

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

    async def _async_update_players(self) -> None:
        """Update players after reconnection."""
        try:
            player_updates = await self.heos.load_players()
        except HeosError as error:
            _LOGGER.error("Unable to refresh players: %s", error)
            return
        # After reconnecting, player_id may have changed
        if player_updates.updated_player_ids:
            self._async_update_player_ids(player_updates.updated_player_ids)
