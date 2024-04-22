"""Coordinator for 17Track."""

from dataclasses import dataclass
from typing import Any

from py17track import Client as SeventeenTrackClient
from py17track.errors import SeventeenTrackError
from py17track.package import Package

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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

    summary: dict[str, dict[str, Any]]
    live_packages: dict[str, Package]


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

    async def _async_update_data(self) -> SeventeenTrackData:
        """Fetch data from 17Track API."""

        summary_dict = {}
        live_packages_dict = {}

        try:
            summary = await self._client.profile.summary(
                show_archived=self._show_archived
            )

        except SeventeenTrackError as err:
            raise UpdateFailed(err) from err

        for status, quantity in summary.items():
            summary_dict[slugify(status)] = {
                "quantity": quantity,
                "packages": [],
                "status_name": status,
            }

        try:
            live_packages = set(
                await self._client.profile.packages(show_archived=self._show_archived)
            )
        except SeventeenTrackError as err:
            raise UpdateFailed(err) from err

        for package in live_packages:
            live_packages_dict[package.tracking_number] = package
            summary_value = summary_dict.get(slugify(package.status))
            if summary_value:
                summary_value["packages"].append(package)

        return SeventeenTrackData(
            summary=summary_dict, live_packages=live_packages_dict
        )
