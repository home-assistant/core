"""Coordinator for the Concord232 integration."""

from dataclasses import dataclass
import logging
from typing import Any, override

from concord232 import client as concord232_client
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type Concord232ConfigEntry = ConfigEntry[Concord232Coordinator]


@dataclass
class Concord232Data:
    """Data fetched from the Concord232 server."""

    partitions: list[dict[str, Any]]
    zones: list[dict[str, Any]]


class Concord232Coordinator(DataUpdateCoordinator[Concord232Data]):
    """Poll partitions and zones from the Concord232 server."""

    config_entry: Concord232ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: Concord232ConfigEntry,
        client: concord232_client.Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> Concord232Data:
        """Fetch partitions and zones."""
        return await self.hass.async_add_executor_job(self._fetch)

    def _fetch(self) -> Concord232Data:
        """Fetch from the blocking client."""
        try:
            partitions = self.client.list_partitions()
            zones = self.client.list_zones()
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Unable to reach the Concord232 server: {err}") from err
        # Zone order can vary between responses; sort so unnamed zones map to
        # stable entities.
        zones.sort(key=lambda zone: zone["number"])
        return Concord232Data(partitions=partitions, zones=zones)
