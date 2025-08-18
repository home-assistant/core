"""Volvo coordinators."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, cast

from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import (
    VolvoApiException,
    VolvoAuthException,
    VolvoCarsApiBaseModel,
    VolvoCarsValue,
    VolvoCarsVehicle,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_BATTERY_CAPACITY, DOMAIN

VERY_SLOW_INTERVAL = 60
SLOW_INTERVAL = 15
MEDIUM_INTERVAL = 2

_LOGGER = logging.getLogger(__name__)


type VolvoConfigEntry = ConfigEntry[tuple[VolvoBaseCoordinator, ...]]
type CoordinatorData = dict[str, VolvoCarsApiBaseModel | None]


class VolvoBaseCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Volvo base coordinator."""

    config_entry: VolvoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        api: VolvoCarsApi,
        vehicle: VolvoCarsVehicle,
        update_interval: timedelta,
        name: str,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=update_interval,
        )

        self.api = api
        self.vehicle = vehicle

        self._api_calls: list[Callable[[], Coroutine[Any, Any, Any]]] = []

    async def _async_setup(self) -> None:
        self._api_calls = await self._async_determine_api_calls()

        if not self._api_calls:
            self.update_interval = None

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from API."""

        data: CoordinatorData = {}

        if not self._api_calls:
            return data

        valid = False
        exception: Exception | None = None

        results = await asyncio.gather(
            *(call() for call in self._api_calls), return_exceptions=True
        )

        for result in results:
            if isinstance(result, VolvoAuthException):
                # If one result is a VolvoAuthException, then probably all requests
                # will fail. In this case we can cancel everything to
                # reauthenticate.
                #
                # Raising ConfigEntryAuthFailed will cancel future updates
                # and start a config flow with SOURCE_REAUTH (async_step_reauth)
                _LOGGER.debug(
                    "%s - Authentication failed. %s",
                    self.config_entry.entry_id,
                    result.message,
                )
                raise ConfigEntryAuthFailed(
                    f"Authentication failed. {result.message}"
                ) from result

            if isinstance(result, VolvoApiException):
                # Maybe it's just one call that fails. Log the error and
                # continue processing the other calls.
                _LOGGER.debug(
                    "%s - Error during data update: %s",
                    self.config_entry.entry_id,
                    result.message,
                )
                exception = exception or result
                continue

            if isinstance(result, Exception):
                # Something bad happened, raise immediately.
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                ) from result

            data |= cast(CoordinatorData, result)
            valid = True

        # Raise an error if not a single API call succeeded
        if not valid:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from exception

        return data

    def get_api_field(self, api_field: str | None) -> VolvoCarsApiBaseModel | None:
        """Get the API field based on the entity description."""

        return self.data.get(api_field) if api_field else None

    @abstractmethod
    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        raise NotImplementedError


class VolvoVerySlowIntervalCoordinator(VolvoBaseCoordinator):
    """Volvo coordinator with very slow update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        api: VolvoCarsApi,
        vehicle: VolvoCarsVehicle,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            api,
            vehicle,
            timedelta(minutes=VERY_SLOW_INTERVAL),
            "Volvo very slow interval coordinator",
        )

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        return [
            self.api.async_get_diagnostics,
            self.api.async_get_odometer,
            self.api.async_get_statistics,
        ]

    async def _async_update_data(self) -> CoordinatorData:
        data = await super()._async_update_data()

        # Add static values
        if self.vehicle.has_battery_engine():
            data[DATA_BATTERY_CAPACITY] = VolvoCarsValue.from_dict(
                {
                    "value": self.vehicle.battery_capacity_kwh,
                }
            )

        return data


class VolvoSlowIntervalCoordinator(VolvoBaseCoordinator):
    """Volvo coordinator with slow update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        api: VolvoCarsApi,
        vehicle: VolvoCarsVehicle,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            api,
            vehicle,
            timedelta(minutes=SLOW_INTERVAL),
            "Volvo slow interval coordinator",
        )

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        if self.vehicle.has_combustion_engine():
            return [
                self.api.async_get_command_accessibility,
                self.api.async_get_fuel_status,
            ]

        return [self.api.async_get_command_accessibility]


class VolvoMediumIntervalCoordinator(VolvoBaseCoordinator):
    """Volvo coordinator with medium update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        api: VolvoCarsApi,
        vehicle: VolvoCarsVehicle,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            api,
            vehicle,
            timedelta(minutes=MEDIUM_INTERVAL),
            "Volvo medium interval coordinator",
        )

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        if self.vehicle.has_battery_engine():
            capabilities = await self.api.async_get_energy_capabilities()

            if capabilities.get("isSupported", False):
                return [self.api.async_get_energy_state]

        return []
