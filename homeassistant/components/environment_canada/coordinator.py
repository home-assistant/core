"""Coordinator for the Environment Canada (EC) component."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TypeVar
import xml.etree.ElementTree as ET

from env_canada import ECAirQuality, ECRadar, ECWeather, ec_exc

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type ECConfigEntry = ConfigEntry[ECRuntimeData]
ECDataTypeT = TypeVar("ECDataTypeT", bound=ECAirQuality | ECRadar | ECWeather)


@dataclass
class ECRuntimeData:
    """Class to hold EC runtime data."""

    aqhi_coordinator: ECDataUpdateCoordinator[ECAirQuality]
    radar_coordinator: ECDataUpdateCoordinator[ECRadar]
    weather_coordinator: ECDataUpdateCoordinator[ECWeather]


class ECDataUpdateCoordinator[ECDataTypeT](DataUpdateCoordinator[ECDataTypeT]):
    """Class to manage fetching EC data."""

    config_entry: ECConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ECConfigEntry,
        ec_data: ECDataTypeT,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize global EC data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {name}",
            update_interval=update_interval,
        )
        self.ec_data = ec_data
        self.last_update_success = False

    async def _async_update_data(self) -> ECDataTypeT:
        """Fetch data from EC."""
        try:
            await self.ec_data.update()
        except (ET.ParseError, ec_exc.UnknownStationId) as ex:
            raise UpdateFailed(f"Error fetching {self.name} data: {ex}") from ex
        return self.ec_data
