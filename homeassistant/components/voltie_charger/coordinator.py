"""Data update coordinator for Voltie chargers."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import override

from voltie import (
    Status,
    VoltieAuthenticationError,
    VoltieCharger,
    VoltieConnectionError,
    VoltieError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_SCAN_INTERVAL, DOMAIN, LOGGER, MIN_API_VERSION


@dataclass(kw_only=True)
class VoltieRuntimeData:
    """Data of a set-up charger."""

    charger: VoltieCharger
    data_coordinator: VoltieDataUpdateCoordinator


type VoltieChargerConfigEntry = ConfigEntry[VoltieRuntimeData]


@dataclass(frozen=True, kw_only=True)
class VoltieChargerData:
    """Live data of a charger."""

    status: Status


class VoltieDataUpdateCoordinator(DataUpdateCoordinator[VoltieChargerData]):
    """Polls the live status of the charger."""

    config_entry: VoltieChargerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VoltieChargerConfigEntry,
        charger: VoltieCharger,
    ) -> None:
        """Initialize the coordinator."""
        self.charger = charger
        self.api_version: int | None = None
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} status",
            update_interval=DATA_SCAN_INTERVAL,
        )

    @override
    async def _async_setup(self) -> None:
        """Refuse firmware whose HTTP API is too old for this integration."""
        self.api_version = await self._async_call(self.charger.api_version())
        if (self.api_version or 0) < MIN_API_VERSION:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_firmware",
            )

    @override
    async def _async_update_data(self) -> VoltieChargerData:
        """Fetch the live data from the charger."""
        status = await self._async_call(self.charger.status())
        if status.charger_id != self.config_entry.unique_id:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="wrong_charger",
                translation_placeholders={"host": self.charger.host},
            )
        return VoltieChargerData(status=status)

    async def _async_call[_ResultT](self, request: Awaitable[_ResultT]) -> _ResultT:
        """Await a request to the charger, raising update errors on failure."""
        try:
            return await request
        except VoltieAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except VoltieConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except VoltieError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err
