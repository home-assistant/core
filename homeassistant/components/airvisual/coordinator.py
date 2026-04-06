"""Define an AirVisual data coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pyairvisual.cloud_api import (
    CloudAPI,
    InvalidKeyError,
    KeyExpiredError,
    UnauthorizedError,
)
from pyairvisual.errors import AirVisualError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LATITUDE, CONF_LONGITUDE, CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CITY, LOGGER

type AirVisualConfigEntry = ConfigEntry[AirVisualDataUpdateCoordinator]


class AirVisualDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching AirVisual data."""

    config_entry: AirVisualConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirVisualConfigEntry,
        cloud_api: CloudAPI,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        self._cloud_api = cloud_api
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=name,
            # We give a placeholder update interval in order to create the coordinator;
            # then, in async_setup_entry, we use the coordinator's presence (along with
            # any other coordinators using the same API key) to calculate an actual,
            # leveled update interval:
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get new data from the API."""
        if CONF_CITY in self.config_entry.data:
            api_coro = self._cloud_api.air_quality.city(
                self.config_entry.data[CONF_CITY],
                self.config_entry.data[CONF_STATE],
                self.config_entry.data[CONF_COUNTRY],
            )
        else:
            api_coro = self._cloud_api.air_quality.nearest_city(
                self.config_entry.data[CONF_LATITUDE],
                self.config_entry.data[CONF_LONGITUDE],
            )

        try:
            return await api_coro
        except (InvalidKeyError, KeyExpiredError, UnauthorizedError) as ex:
            raise ConfigEntryAuthFailed from ex
        except AirVisualError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err
