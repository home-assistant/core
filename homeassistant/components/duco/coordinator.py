"""Data update coordinator for the Duco integration."""

from __future__ import annotations

import asyncio
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
type DucoData = dict[int, Node]


class DucoCoordinator(DataUpdateCoordinator[DucoData]):
    """Coordinator for the Duco integration."""

    config_entry: DucoConfigEntry
    board_info: BoardInfo
    rssi_wifi: int | None
    write_req_remaining: int | None

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
        self.rssi_wifi = None
        self.write_req_remaining = None

    async def _async_setup(self) -> None:
        """Fetch board info once during initial setup."""
        try:
            self.board_info = await self.client.async_get_board_info()
        except DucoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except DucoError as err:
            raise ConfigEntryError(f"Duco API error: {err}") from err

    async def _async_update_data(self) -> DucoData:
        """Fetch node data from the Duco box."""
        nodes_result, lan_result, write_result = await asyncio.gather(
            self.client.async_get_nodes(),
            self.client.async_get_lan_info(),
            self.client.async_get_write_req_remaining(),
            return_exceptions=True,
        )

        if isinstance(nodes_result, DucoConnectionError):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(nodes_result)},
            ) from nodes_result
        if isinstance(nodes_result, BaseException):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": repr(nodes_result)},
            ) from nodes_result

        if not isinstance(lan_result, BaseException):
            self.rssi_wifi = lan_result.rssi_wifi

        if not isinstance(write_result, BaseException):
            self.write_req_remaining = write_result

        return {node.node_id: node for node in nodes_result}
