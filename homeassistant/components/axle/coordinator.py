"""Coordinate Axle event updates."""

import logging
from typing import override

from aioaxlevpp import AxleAuthenticationError, AxleClient, AxleError, GridEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
type AxleConfigEntry = ConfigEntry[AxleCoordinator]


class AxleCoordinator(DataUpdateCoordinator[GridEvent | None]):
    """Fetch one event using the provider's documented polling interval."""

    config_entry: AxleConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AxleConfigEntry, client: AxleClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> GridEvent | None:
        """Fetch the event without confusing outages with an empty schedule."""
        try:
            event = await self.client.get_event()
        except AxleAuthenticationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except AxleError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        return None if event is not None and event.opted_out else event
