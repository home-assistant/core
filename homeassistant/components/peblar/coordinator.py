"""Data update coordinator for Peblar EV chargers."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Concatenate

from peblar import (
    AccessMode,
    Peblar,
    PeblarApi,
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
    PeblarEVInterface,
    PeblarMeter,
    PeblarSystem,
    PeblarSystemInformation,
    PeblarUserConfiguration,
    PeblarVersions,
)

from homeassistant.const import CONF_PASSWORD
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass(kw_only=True)
class PeblarRuntimeData:
    """Class to hold runtime data."""

    data_coordinator: PeblarDataUpdateCoordinator
    last_known_charging_limit = 6
    system_information: PeblarSystemInformation
    user_configuration_coordinator: PeblarUserConfigurationDataUpdateCoordinator
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


def _coordinator_exception_handler[
    _DataUpdateCoordinatorT: PeblarDataUpdateCoordinator
    | PeblarVersionDataUpdateCoordinator
    | PeblarUserConfigurationDataUpdateCoordinator,
    **_P,
](
    func: Callable[Concatenate[_DataUpdateCoordinatorT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_DataUpdateCoordinatorT, _P], Coroutine[Any, Any, Any]]:
    """Handle exceptions within the update handler of a coordinator."""

    async def handler(
        self: _DataUpdateCoordinatorT, *args: _P.args, **kwargs: _P.kwargs
    ) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except PeblarAuthenticationError as error:
            entry = getattr(self, "config_entry", None)
            peblar_obj = getattr(self, "peblar", None)

            if entry and peblar_obj and not getattr(self, "_reauth_lock", False):
                try:
                    self._reauth_lock = True
                    await peblar_obj.login(password=entry.data[CONF_PASSWORD])

                    after = getattr(self, "_async_after_reauth", None)
                    if callable(after):
                        await after()

                    # 1 retry after succesfull login
                    return await func(self, *args, **kwargs)
                finally:
                    self._reauth_lock = False

            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except PeblarConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error
        except PeblarError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler


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

    @_coordinator_exception_handler
    async def _async_update_data(self) -> PeblarVersionInformation:
        """Fetch data from the Peblar device."""
        return PeblarVersionInformation(
            current=await self.peblar.current_versions(),
            available=await self.peblar.available_versions(),
        )


class PeblarDataUpdateCoordinator(DataUpdateCoordinator[PeblarData]):
    """Class to manage fetching Peblar active data."""

    config_entry: PeblarConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PeblarConfigEntry, peblar: Peblar, api: PeblarApi
    ) -> None:
        """Initialize the coordinator."""
        self.peblar = peblar
        self.api = api
        self._reauth_lock = False
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Peblar {entry.title} meter",
            update_interval=timedelta(seconds=10),
        )

    async def _async_after_reauth(self) -> None:
        # After relogin: rebuild API object
        self.api = await self.peblar.rest_api(enable=True, access_mode=AccessMode.READ_WRITE)

    @_coordinator_exception_handler
    async def _async_update_data(self) -> PeblarData:
        """Fetch data from the Peblar device."""
        return PeblarData(
            ev=await self.api.ev_interface(),
            meter=await self.api.meter(),
            system=await self.api.system(),
        )


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

    @_coordinator_exception_handler
    async def _async_update_data(self) -> PeblarUserConfiguration:
        """Fetch data from the Peblar device."""
        return await self.peblar.user_configuration()
