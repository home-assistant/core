"""Data update coordinator for the Duco integration."""

from __future__ import annotations

import logging

from duco import DucoClient
from duco.exceptions import DucoConnectionError, DucoError
from duco.models import BoardInfo, Node

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type DucoConfigEntry = ConfigEntry[DucoCoordinator]


class DucoCoordinator(DataUpdateCoordinator[dict[int, Node]]):
    """Coordinator for the Duco integration."""

    config_entry: DucoConfigEntry
    board_info: BoardInfo

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DucoConfigEntry,
        client: DucoClient,
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

    async def _async_setup(self) -> None:
        """Fetch board info once during initial setup."""
        try:
            self.board_info = await self.client.async_get_board_info()
        except DucoConnectionError as err:
            raise UpdateFailed(f"Cannot connect to Duco box: {err}") from err
        except DucoError as err:
            raise ConfigEntryError(f"Duco API error: {err}") from err

    async def _async_update_data(self) -> dict[int, Node]:
        """Fetch node data from the Duco box."""
        try:
            nodes = await self.client.async_get_nodes()
        except DucoConnectionError as err:
            raise UpdateFailed(f"Cannot connect to Duco box: {err}") from err
        except DucoError as err:
            raise UpdateFailed(f"Duco API error: {err}") from err
        return {node.node_id: node for node in nodes}
