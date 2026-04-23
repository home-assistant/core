"""Data update coordinator for the Duco integration."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class DucoData:
    """Data returned by the Duco coordinator."""

    nodes: dict[int, Node]
    rssi_wifi: int | None


class DucoCoordinator(DataUpdateCoordinator[DucoData]):
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

        return DucoData(
            nodes={node.node_id: node for node in nodes},
            rssi_wifi=lan_info.rssi_wifi,
        )

    async def async_refresh_nodes(self) -> None:
        """Fetch only node data, reusing the last known rssi_wifi value."""
        try:
            nodes = await self.client.async_get_nodes()
        except DucoConnectionError, DucoError:
            return
        if self.data is not None:
            self.async_set_updated_data(
                DucoData(
                    nodes={node.node_id: node for node in nodes},
                    rssi_wifi=self.data.rssi_wifi,
                )
            )
