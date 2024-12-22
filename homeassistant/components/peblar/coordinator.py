"""Data update coordinator for Peblar EV chargers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from peblar import (
    Peblar,
    PeblarApi,
    PeblarError,
    PeblarEVInterface,
    PeblarMeter,
    PeblarSystem,
    PeblarUserConfiguration,
    PeblarVersions,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from tests.components.peblar.conftest import PeblarSystemInformation

from .const import LOGGER


@dataclass(kw_only=True)
class PeblarRuntimeData:
    """Class to hold runtime data."""

    data_coordinator: PeblarDataUpdateCoordinator
    system_information: PeblarSystemInformation
    user_configuraton_coordinator: PeblarUserConfigurationDataUpdateCoordinator
    version_coordinator: PeblarVersionDataUpdateCoordinator


type PeblarConfigEntry = ConfigEntry[PeblarRuntimeData]


@dataclass(kw_only=True, frozen=True)
class PeblarVersionInformation:
    """Class to hold version information."""

    current: PeblarVersions
    available: PeblarVersions


@dataclass(kw_only=True)
class PeblarData:
    """Class to hold active charging related information of Peblar.

    This is data that needs to be polled and updated at a relatively high
    frequency in order for this integration to function correctly.
    All this data is updated at the same time by a single coordinator.
    """

    ev: PeblarEVInterface
    meter: PeblarMeter
    system: PeblarSystem


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


class PeblarDataUpdateCoordinator(DataUpdateCoordinator[PeblarData]):
    """Class to manage fetching Peblar active data."""

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

    async def _async_update_data(self) -> PeblarData:
        """Fetch data from the Peblar device."""
        try:
            return PeblarData(
                ev=await self.api.ev_interface(),
                meter=await self.api.meter(),
                system=await self.api.system(),
            )
        except PeblarError as err:
            raise UpdateFailed(err) from err


class PeblarUserConfigurationDataUpdateCoordinator(
    DataUpdateCoordinator[PeblarUserConfiguration]
):
    """Class to manage fetching Peblar user configuration data."""

    def __init__(
        self, hass: HomeAssistant, entry: PeblarConfigEntry, peblar: Peblar
    ) -> None:
        """Initialize the coordinator."""
        self.peblar = peblar
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Peblar {entry.title} user configuration",
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> PeblarUserConfiguration:
        """Fetch data from the Peblar device."""
        try:
            return await self.peblar.user_configuration()
        except PeblarError as err:
            raise UpdateFailed(err) from err
