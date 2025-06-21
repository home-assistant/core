"""Volvo coordinators."""

from __future__ import annotations

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

_LOGGER = logging.getLogger(__name__)


type VolvoConfigEntry = ConfigEntry[tuple[VolvoBaseCoordinator, ...]]
type CoordinatorData = dict[str, VolvoCarsApiBaseModel | None]


class VolvoBaseCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Volvo base coordinator."""

    config_entry: VolvoConfigEntry
    vehicle: VolvoCarsVehicle

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        api: VolvoCarsApi,
        vehicle: VolvoCarsVehicle,
        update_interval: timedelta,
        name: str,
        api_calls: list[str],
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
        self._api_calls = api_calls

        self._refresh_conditions = {
            "command_accessibility": (self.api.async_get_command_accessibility, True),
            "diagnostics": (self.api.async_get_diagnostics, True),
            "fuel": (
                self.api.async_get_fuel_status,
                self.vehicle.has_combustion_engine(),
            ),
            "odometer": (self.api.async_get_odometer, True),
            "recharge_status": (
                self.api.async_get_recharge_status,
                self.vehicle.has_battery_engine(),
            ),
            "statistics": (self.api.async_get_statistics, True),
        }

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from API."""

        api_calls = self._get_api_calls()
        data: CoordinatorData = {}

        if not api_calls:
            return data

        valid = False
        exception: Exception | None = None

        results = await asyncio.gather(
            *(call() for call in api_calls), return_exceptions=True
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

    def _get_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        return [
            api_call
            for key, (api_call, condition) in self._refresh_conditions.items()
            if condition and key in self._api_calls
        ]


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
            timedelta(minutes=60),
            "Volvo very slow interval coordinator",
            ["diagnostics", "odometer", "statistics"],
        )

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
            timedelta(minutes=15),
            "Volvo slow interval coordinator",
            ["command_accessibility", "fuel"],
        )


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
            timedelta(minutes=2),
            "Volvo medium interval coordinator",
            ["recharge_status"],
        )
