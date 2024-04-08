"""Coordinator for 17Track."""

from dataclasses import dataclass
from typing import Any

from py17track import Client as SeventeenTrackClient
from py17track.errors import SeventeenTrackError
from py17track.package import Package

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)


@dataclass
class SeventeenTrackData:
    """Class for handling the data retrieval."""

    def __init__(self) -> None:
        """Initialize the data object."""
        self.summary: dict[str, dict[str, Any]] = {}
        self.live_packages: dict[str, Package] = {}


class SeventeenTrackCoordinator(DataUpdateCoordinator[SeventeenTrackData]):
    """Class to manage fetching 17Track data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: SeventeenTrackClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.show_delivered = self.config_entry.options[CONF_SHOW_DELIVERED]
        self.account_id = client.profile.account_id

        self._show_archived = self.config_entry.options[CONF_SHOW_ARCHIVED]
        self._client = client

    async def _async_update_data(
        self,
    ) -> SeventeenTrackData:
        """Fetch data from 17Track API."""

        data = SeventeenTrackData()
        summary = {}
        live_packages = set()

        try:
            summary = await self._client.profile.summary(
                show_archived=self._show_archived
            )

        except SeventeenTrackError as err:
            LOGGER.error("There was an error retrieving the summary: %s", err)

        for status, quantity in summary.items():
            data.summary[slugify(status)] = {
                "quantity": quantity,
                "packages": [],
                "status_name": status,
            }

        try:
            live_packages = set(
                await self._client.profile.packages(show_archived=self._show_archived)
            )
        except SeventeenTrackError as err:
            LOGGER.error("There was an error retrieving the packages: %s", err)

        data.live_packages.clear()

        for package in live_packages:
            data.live_packages[package.tracking_number] = package
            summary_value = data.summary.get(slugify(package.status))
            if summary_value:
                summary_value["packages"].append(package)

        return data
