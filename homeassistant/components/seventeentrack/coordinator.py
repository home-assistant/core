"""Coordinator for 17Track."""

from dataclasses import dataclass
from typing import Any

from py17track import Client as SeventeenTrackClient
from py17track.errors import SeventeenTrackError
from py17track.package import Package

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import (
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_TYPE,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
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
        self.current_packages: dict[str, dict[str, Any]] = {}
        self.new_packages: dict[str, Package] = {}
        self.old_packages: set[Package] = set()


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
        self._show_archived = self.config_entry.options[CONF_SHOW_ARCHIVED]
        self._show_delivered = self.config_entry.options[CONF_SHOW_DELIVERED]
        self._client = client
        self._account_id = client.profile.account_id
        self._packages: set[Package] = set()

    async def _async_update_data(
        self,
    ) -> SeventeenTrackData:
        """Fetch data from 17Track API."""

        data = SeventeenTrackData()
        summary = {}
        current_packages = set()

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
            }

        try:
            current_packages = set(
                await self._client.profile.packages(show_archived=self._show_archived)
            )
        except SeventeenTrackError as err:
            LOGGER.error("There was an error retrieving the packages: %s", err)

        # Packages in new_packages but not in self._packages
        packages_to_add = current_packages - self._packages

        # Packages in self._packages but not in new_packages
        packages_to_remove = self._packages - current_packages

        data.old_packages = packages_to_remove

        self._packages = (self._packages | packages_to_add) - packages_to_remove

        for package in current_packages:
            data.current_packages[package.tracking_number] = {
                "package": package,
                "extra": {
                    ATTR_DESTINATION_COUNTRY: package.destination_country,
                    ATTR_INFO_TEXT: package.info_text,
                    ATTR_TIMESTAMP: package.timestamp,
                    ATTR_LOCATION: package.location,
                    ATTR_ORIGIN_COUNTRY: package.origin_country,
                    ATTR_PACKAGE_TYPE: package.package_type,
                    ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
                    ATTR_TRACKING_NUMBER: package.tracking_number,
                },
            }
            summary_value = data.summary.get(slugify(package.status))
            if summary_value:
                summary_value["packages"].append(
                    {
                        ATTR_TRACKING_NUMBER: package.tracking_number,
                        ATTR_LOCATION: package.location,
                        ATTR_STATUS: package.status,
                        ATTR_TIMESTAMP: package.timestamp,
                        ATTR_INFO_TEXT: package.info_text,
                        ATTR_FRIENDLY_NAME: package.friendly_name,
                    }
                )
            if package in packages_to_add:
                data.new_packages[package.tracking_number] = package

        return data

    @property
    def show_delivered(self):
        """Return whether delivered packages should be shown."""
        return self._show_delivered

    @property
    def account_id(self):
        """Return the account ID."""
        return self._account_id
