"""Data update coordinator for the Duco integration."""

from __future__ import annotations

import logging

from duco import DucoClient
from duco.exceptions import DucoConnectionError, DucoError
from duco.models import BoardInfo, LanInfo, Node

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
    lan_info: LanInfo | None
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
        try:
            nodes = await self.client.async_get_nodes()
        except DucoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except DucoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": repr(err)},
            ) from err

        try:
            lan_info = await self.client.async_get_lan_info()
            self.rssi_wifi = lan_info.rssi_wifi
        except DucoError:
            self.rssi_wifi = None

        try:
            self.write_req_remaining = await self.client.async_get_write_req_remaining()
        except DucoError:
            self.write_req_remaining = None

        return {node.node_id: node for node in nodes}
