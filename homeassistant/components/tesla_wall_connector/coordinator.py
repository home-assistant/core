"""DataUpdateCoordinator for the Tesla Wall Connector integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import (
    WallConnectorConnectionError,
    WallConnectorConnectionTimeoutError,
    WallConnectorError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    WALLCONNECTOR_DATA_LIFETIME,
    WALLCONNECTOR_DATA_VITALS,
    WALLCONNECTOR_DATA_WIFI_STATUS,
)

_LOGGER = logging.getLogger(__name__)

type WallConnectorConfigEntry = ConfigEntry[WallConnectorData]


@dataclass
class WallConnectorData:
    """Data for the Tesla Wall Connector integration."""

    wall_connector_client: WallConnector
    update_coordinator: WallConnectorCoordinator
    hostname: str
    part_number: str
    firmware_version: str
    serial_number: str


class WallConnectorCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Tesla Wall Connector data."""

    config_entry: WallConnectorConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WallConnectorConfigEntry,
        hostname: str,
        wall_connector: WallConnector,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="tesla-wallconnector",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._hostname = hostname
        self._wall_connector = wall_connector

    @override
    async def _async_update_data(self) -> dict:
        """Fetch new data from the Wall Connector."""
        try:
            vitals, lifetime, wifi_status = await asyncio.gather(
                self._wall_connector.async_get_vitals(),
                self._wall_connector.async_get_lifetime(),
                self._wall_connector.async_get_wifi_status(),
            )
        except WallConnectorConnectionTimeoutError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {self._hostname}:"
                " Timeout"
            ) from ex
        except WallConnectorConnectionError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {self._hostname}:"
                " Cannot connect"
            ) from ex
        except WallConnectorError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {self._hostname}:"
                f" {ex}"
            ) from ex

        return {
            WALLCONNECTOR_DATA_VITALS: vitals,
            WALLCONNECTOR_DATA_LIFETIME: lifetime,
            WALLCONNECTOR_DATA_WIFI_STATUS: wifi_status,
        }
