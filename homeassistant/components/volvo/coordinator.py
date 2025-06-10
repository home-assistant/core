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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_BATTERY_CAPACITY, DOMAIN

_LOGGER = logging.getLogger(__name__)


type VolvoConfigEntry = ConfigEntry[VolvoDataCoordinator]
type CoordinatorData = dict[str, VolvoCarsApiBaseModel | None]


class VolvoDataCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Volvo Data Coordinator."""

    config_entry: VolvoConfigEntry
    vehicle: VolvoCarsVehicle

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        api: VolvoCarsApi,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=135),
        )

        self.api = api

        # The variable is set during _async_setup().
        self._refresh_conditions: dict[
            str, tuple[Callable[[], Coroutine[Any, Any, Any]], bool]
        ] = {}

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        This method is called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        try:
            vehicle = await self.api.async_get_vehicle_details()
        except VolvoAuthException as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="unauthorized",
                translation_placeholders={"message": ex.message},
            ) from ex

        if vehicle is None:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="no_vehicle"
            )

        self.vehicle = vehicle
        self.data = {}

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

        # Add static values
        data[DATA_BATTERY_CAPACITY] = VolvoCarsValue.from_dict(
            {
                "value": self.vehicle.battery_capacity_kwh,
            }
        )

        return data

    def get_api_field(self, api_field: str | None) -> VolvoCarsApiBaseModel | None:
        """Get the API field based on the entity description."""

        return self.data.get(api_field) if api_field else None

    def _get_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        return [
            api_call
            for _, (api_call, condition) in self._refresh_conditions.items()
            if condition
        ]
