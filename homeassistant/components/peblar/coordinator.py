"""Data update coordinator for Peblar EV chargers."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Concatenate, override

from peblar import (
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

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_RESTART_TIMEOUT


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
            if self.config_entry and self.config_entry.state is ConfigEntryState.LOADED:
                # This is not the first refresh, so let's reload
                # the config entry to ensure we trigger a re-authentication
                # flow (or recover in case of API token changes).
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
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

    config_entry: PeblarConfigEntry

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
    @override
    async def _async_update_data(self) -> PeblarVersionInformation:
        """Fetch data from the Peblar device."""
        return PeblarVersionInformation(
            current=await self.peblar.current_versions(),
            available=await self.peblar.available_versions(),
        )

    @callback
    def async_refresh_after_restart(self) -> None:
        """Read the versions again once the charger has restarted.

        Installing a package returns long before the charger is done: it
        downloads, then reboots on its own, which Peblar's own web
        interface allows hours for. Rather than guess at a delay, wait for
        the charger to drop off and come back, which the data poll notices
        every ten seconds. Peblar waits for the same two moments.

        Without this a charger that just updated keeps offering the update
        it already took, until the two hourly version poll comes round.
        """
        entry = self.config_entry
        data_coordinator = entry.runtime_data.data_coordinator
        went_down = False
        unsubscribes: list[CALLBACK_TYPE] = []

        @callback
        def _stop_waiting() -> None:
            while unsubscribes:
                unsubscribes.pop()()

        @callback
        def _give_up(_now: datetime) -> None:
            """Stop waiting for a charger that never came back."""
            _stop_waiting()

        @callback
        def _handle_data_coordinator_update() -> None:
            nonlocal went_down
            if not data_coordinator.last_update_success:
                went_down = True
                return

            # Still reachable, so the charger has not started rebooting yet.
            if not went_down:
                return

            _stop_waiting()
            entry.async_create_task(
                self.hass, self.async_request_refresh(), eager_start=False
            )

        unsubscribes.append(
            data_coordinator.async_add_listener(_handle_data_coordinator_update)
        )
        unsubscribes.append(
            async_call_later(self.hass, UPDATE_RESTART_TIMEOUT, _give_up)
        )
        entry.async_on_unload(_stop_waiting)


class PeblarDataUpdateCoordinator(DataUpdateCoordinator[PeblarData]):
    """Class to manage fetching Peblar active data."""

    config_entry: PeblarConfigEntry

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

    @_coordinator_exception_handler
    @override
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
    @override
    async def _async_update_data(self) -> PeblarUserConfiguration:
        """Fetch data from the Peblar device."""
        return await self.peblar.user_configuration()
