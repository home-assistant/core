"""Data update coordinator for the Duco integration."""

from __future__ import annotations

import logging

from duco import DucoClient
from duco.exceptions import DucoConnectionError, DucoError
from duco.models import BoardInfo, Node

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type DucoConfigEntry = ConfigEntry[DucoCoordinator]


class DucoCoordinator(DataUpdateCoordinator[list[Node]]):
    """Coordinator for the Duco integration."""

    config_entry: DucoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DucoConfigEntry,
        client: DucoClient,
        board_info: BoardInfo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.board_info = board_info

    async def _async_update_data(self) -> list[Node]:
        """Fetch node data from the Duco box."""
        try:
            return await self.client.async_get_nodes()
        except DucoConnectionError as err:
            raise UpdateFailed(f"Cannot connect to Duco box: {err}") from err
        except DucoError as err:
            raise UpdateFailed(f"Duco API error: {err}") from err
