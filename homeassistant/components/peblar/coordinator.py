"""Data update coordinator for Peblar EV chargers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from peblar import Peblar, PeblarApi, PeblarError, PeblarMeter, PeblarVersions

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from tests.components.peblar.conftest import PeblarSystemInformation

from .const import LOGGER


@dataclass(kw_only=True)
class PeblarRuntimeData:
    """Class to hold runtime data."""

    system_information: PeblarSystemInformation
    meter_coordinator: PeblarMeterDataUpdateCoordinator
    version_coordinator: PeblarVersionDataUpdateCoordinator


type PeblarConfigEntry = ConfigEntry[PeblarRuntimeData]


@dataclass(kw_only=True, frozen=True)
class PeblarVersionInformation:
    """Class to hold version information."""

    current: PeblarVersions
    available: PeblarVersions


class PeblarVersionDataUpdateCoordinator(
    DataUpdateCoordinator[PeblarVersionInformation]
):
    """Class to manage fetching Peblar version information."""

    def __init__(
        self, hass: HomeAssistant, entry: PeblarConfigEntry, peblar: Peblar
    ) -> None:
        """Initialize the coordinator."""
        self.peblar = peblar
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Peblar {entry.title} version",
            update_interval=timedelta(hours=2),
        )

    async def _async_update_data(self) -> PeblarVersionInformation:
        """Fetch data from the Peblar device."""
        try:
            return PeblarVersionInformation(
                current=await self.peblar.current_versions(),
                available=await self.peblar.available_versions(),
            )
        except PeblarError as err:
            raise UpdateFailed(err) from err


class PeblarMeterDataUpdateCoordinator(DataUpdateCoordinator[PeblarMeter]):
    """Class to manage fetching Peblar meter data."""

    def __init__(
        self, hass: HomeAssistant, entry: PeblarConfigEntry, api: PeblarApi
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Peblar {entry.title} meter",
            update_interval=timedelta(seconds=10),
        )

    async def _async_update_data(self) -> PeblarMeter:
        """Fetch data from the Peblar device."""
        try:
            return await self.api.meter()
        except PeblarError as err:
            raise UpdateFailed(err) from err
