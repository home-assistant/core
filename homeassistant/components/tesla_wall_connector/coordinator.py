"""DataUpdateCoordinator for the Tesla Wall Connector integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import (
    WallConnectorConnectionError,
    WallConnectorConnectionTimeoutError,
    WallConnectorError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    WALLCONNECTOR_DATA_LIFETIME,
    WALLCONNECTOR_DATA_VITALS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WallConnectorData:
    """Data for the Tesla Wall Connector integration."""

    wall_connector_client: WallConnector
    update_coordinator: WallConnectorCoordinator
    hostname: str
    part_number: str
    firmware_version: str
    serial_number: str


def get_poll_interval(entry: ConfigEntry) -> timedelta:
    """Get the poll interval from config."""
    return timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )


class WallConnectorCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Tesla Wall Connector data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hostname: str,
        wall_connector: WallConnector,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="tesla-wallconnector",
            update_interval=get_poll_interval(entry),
        )
        self._hostname = hostname
        self._wall_connector = wall_connector

    async def _async_update_data(self) -> dict:
        """Fetch new data from the Wall Connector."""
        try:
            vitals = await self._wall_connector.async_get_vitals()
            lifetime = await self._wall_connector.async_get_lifetime()
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
        }
