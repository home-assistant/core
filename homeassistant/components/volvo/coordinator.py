"""Volvo coordinators."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Generic, TypeVar, cast

from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import (
    VolvoApiException,
    VolvoAuthException,
    VolvoCarsApiBaseModel,
    VolvoCarsValue,
    VolvoCarsValueStatusField,
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
FAST_INTERVAL = 1

_LOGGER = logging.getLogger(__name__)


@dataclass
class VolvoContext:
    """Volvo context."""

    api: VolvoCarsApi
    vehicle: VolvoCarsVehicle


@dataclass
class VolvoRuntimeData:
    """Volvo runtime data."""

    interval_coordinators: tuple[VolvoBaseIntervalCoordinator, ...]


type VolvoConfigEntry = ConfigEntry[VolvoRuntimeData]
type CoordinatorData = dict[str, VolvoCarsApiBaseModel | None]

_T = TypeVar("_T", bound=dict[str, Any])


def _is_invalid_api_field(field: VolvoCarsApiBaseModel | None) -> bool:
    if not field:
        return True

    if isinstance(field, VolvoCarsValueStatusField) and field.status == "ERROR":
        return True

    return False


class VolvoBaseCoordinator(DataUpdateCoordinator[_T], Generic[_T]):
    """Volvo base coordinator."""

    config_entry: VolvoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        context: VolvoContext,
        update_interval: timedelta | None,
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

        self.context = context

    def get_api_field(self, api_field: str | None) -> VolvoCarsApiBaseModel | None:
        """Get the API field based on the entity description."""

        return self.data.get(api_field) if api_field else None


class VolvoBaseIntervalCoordinator(VolvoBaseCoordinator[CoordinatorData]):
    """Volvo base interval coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        context: VolvoContext,
        update_interval: timedelta,
        name: str,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            context,
            update_interval,
            name,
        )

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
                # If one result is a VolvoAuthException, then probably all
                # requests
                # will fail. In this case we can cancel everything to
                # reauthenticate.
                #
                # Raising ConfigEntryAuthFailed will cancel future updates
                # and start a config flow with SOURCE_REAUTH
                # (async_step_reauth)
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

            api_data = cast(CoordinatorData, result)
            data |= {
                key: field
                for key, field in api_data.items()
                if not _is_invalid_api_field(field)
            }

            valid = True

        # Raise an error if not a single API call succeeded
        if not valid:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from exception

        return data

    @abstractmethod
    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        raise NotImplementedError


class VolvoVerySlowIntervalCoordinator(VolvoBaseIntervalCoordinator):
    """Volvo coordinator with very slow update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        context: VolvoContext,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            context,
            timedelta(minutes=VERY_SLOW_INTERVAL),
            "Volvo very slow interval coordinator",
        )

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        api = self.context.api

        return [
            api.async_get_brakes_status,
            api.async_get_diagnostics,
            api.async_get_engine_warnings,
            api.async_get_odometer,
            api.async_get_statistics,
            api.async_get_tyre_states,
            api.async_get_warnings,
        ]

    async def _async_update_data(self) -> CoordinatorData:
        data = await super()._async_update_data()

        # Add static values
        if self.context.vehicle.has_battery_engine():
            data[DATA_BATTERY_CAPACITY] = VolvoCarsValue.from_dict(
                {
                    "value": self.context.vehicle.battery_capacity_kwh,
                }
            )

        return data


class VolvoSlowIntervalCoordinator(VolvoBaseIntervalCoordinator):
    """Volvo coordinator with slow update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        context: VolvoContext,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            context,
            timedelta(minutes=SLOW_INTERVAL),
            "Volvo slow interval coordinator",
        )

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        api = self.context.api

        if self.context.vehicle.has_combustion_engine():
            return [
                api.async_get_command_accessibility,
                api.async_get_fuel_status,
            ]

        return [api.async_get_command_accessibility]


class VolvoMediumIntervalCoordinator(VolvoBaseIntervalCoordinator):
    """Volvo coordinator with medium update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        context: VolvoContext,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            context,
            timedelta(minutes=MEDIUM_INTERVAL),
            "Volvo medium interval coordinator",
        )

        self._supported_capabilities: list[str] = []

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        api_calls: list[Any] = []
        api = self.context.api
        vehicle = self.context.vehicle

        if vehicle.has_battery_engine():
            capabilities = await api.async_get_energy_capabilities()

            if capabilities.get("isSupported", False):

                def _normalize_key(key: str) -> str:
                    return "chargingStatus" if key == "chargingSystemStatus" else key

                self._supported_capabilities = [
                    _normalize_key(key)
                    for key, value in capabilities.items()
                    if isinstance(value, dict) and value.get("isSupported", False)
                ]

                api_calls.append(self._async_get_energy_state)

        if vehicle.has_combustion_engine():
            api_calls.append(api.async_get_engine_status)

        return api_calls

    async def _async_get_energy_state(
        self,
    ) -> dict[str, VolvoCarsValueStatusField | None]:
        def _mark_ok(
            field: VolvoCarsValueStatusField | None,
        ) -> VolvoCarsValueStatusField | None:
            if field:
                field.status = "OK"

            return field

        energy_state = await self.context.api.async_get_energy_state()

        return {
            key: _mark_ok(value)
            for key, value in energy_state.items()
            if key in self._supported_capabilities
        }


class VolvoFastIntervalCoordinator(VolvoBaseIntervalCoordinator):
    """Volvo coordinator with fast update rate."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VolvoConfigEntry,
        context: VolvoContext,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            entry,
            context,
            timedelta(minutes=FAST_INTERVAL),
            "Volvo fast interval coordinator",
        )

    async def _async_determine_api_calls(
        self,
    ) -> list[Callable[[], Coroutine[Any, Any, Any]]]:
        api = self.context.api

        return [
            api.async_get_doors_status,
            api.async_get_window_states,
        ]
