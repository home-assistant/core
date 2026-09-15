"""Data coordinator for the AnyList integration."""

import logging
from typing import override

from aioanylist import AnyListClient, AnyListError, AuthenticationError, Domain
from aioanylist.state import AnyListState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type AnyListConfigEntry = ConfigEntry[AnyListDataUpdateCoordinator]


class AnyListDataUpdateCoordinator(DataUpdateCoordinator[AnyListState]):
    """Coordinate AnyList state and realtime updates."""

    config_entry: AnyListConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AnyListConfigEntry,
        client: AnyListClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.client = client

    @override
    async def _async_setup(self) -> None:
        """Load initial AnyList data and start realtime updates."""
        try:
            self.client.sync.add_listener(self._handle_sync)
            await self.client.load(realtime=True, load_tag_data=False)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except (AnyListError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    @override
    async def _async_update_data(self) -> AnyListState:
        """Return the event-driven AnyList state."""
        return self.client.state

    @callback
    def async_update_from_client(self) -> None:
        """Publish the client's optimistic state after a successful mutation."""
        self.async_set_updated_data(self.client.state)

    async def _handle_sync(self, domains: set[Domain]) -> None:
        """Handle a completed AnyList sync triggered by realtime invalidation."""
        if Domain.SHOPPING_LISTS in domains:
            self.async_set_updated_data(self.client.state)

    @override
    async def async_shutdown(self) -> None:
        """Shut down the AnyList client."""
        try:
            await self.client.close()
        except AnyListError:
            _LOGGER.debug("Error while closing AnyList client", exc_info=True)
        await super().async_shutdown()
