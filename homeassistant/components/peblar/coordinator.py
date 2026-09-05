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
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    LOGGER,
    UPDATE_REBOOT_MINIMUM_DOWNTIME,
    UPDATE_REBOOT_RETURN_TIMEOUT,
    UPDATE_REBOOT_START_TIMEOUT,
)


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

    install_in_progress = False
    """Set while the charger is busy installing a package."""

    def __init__(
        self, hass: HomeAssistant, entry: PeblarConfigEntry, peblar: Peblar
    ) -> None:
        """Initialize the coordinator."""
        self.peblar = peblar
        self._reboot_watcher: _RebootWatcher | None = None
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Peblar {entry.title} version",
            update_interval=timedelta(hours=2),
        )
        entry.async_on_unload(self.async_stop_reboot_watcher)

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
        downloads, then reboots on its own. Rather than guess at a delay,
        wait for the charger to drop off and come back, which the data
        poll notices. Peblar's own web interface waits for the same two
        moments, and allows a different amount of time for each.

        Without this a charger that just updated keeps offering the update
        it already took, until the two hourly version poll comes round.
        """
        # Only ever one at a time: the update component refuses an install
        # while the entity reports one in progress, which it does for as
        # long as a watcher is running.
        self.install_in_progress = True
        self._reboot_watcher = _RebootWatcher(self)
        self._reboot_watcher.async_start()

    @callback
    def async_stop_reboot_watcher(self) -> None:
        """Stop waiting on a reboot, if anything is still waiting on one."""
        if (watcher := self._reboot_watcher) is None:
            return

        # Dropped first, so a watcher stopping itself cannot come back
        # round here and stop itself again.
        self._reboot_watcher = None
        watcher.async_stop()


class _RebootWatcher:
    """Waits out the reboot that follows installing a package.

    Two phases, because they are allowed very different amounts of time:
    the charger downloads before it reboots, so going down at all may take
    hours, while coming back afterwards should take minutes.
    """

    def __init__(self, coordinator: PeblarVersionDataUpdateCoordinator) -> None:
        """Initialize the watcher."""
        self._coordinator = coordinator
        self._entry = coordinator.config_entry
        self._data_coordinator = self._entry.runtime_data.data_coordinator
        self._went_down_at: datetime | None = None
        self._start_deadline: datetime | None = None
        self._unsubscribe_listener: CALLBACK_TYPE | None = None
        self._unsubscribe_timer: CALLBACK_TYPE | None = None

    @callback
    def async_start(self) -> None:
        """Start watching for the charger to go away and come back."""
        self._unsubscribe_listener = self._data_coordinator.async_add_listener(
            self._handle_data_coordinator_update
        )
        self._start_deadline = dt_util.utcnow() + UPDATE_REBOOT_START_TIMEOUT
        self._async_set_deadline(UPDATE_REBOOT_START_TIMEOUT)

    @callback
    def _async_set_deadline(self, timeout: timedelta) -> None:
        """Give up if nothing happens within the given time."""
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
        self._unsubscribe_timer = async_call_later(
            self._coordinator.hass, timeout, self._handle_deadline
        )

    @callback
    def _handle_deadline(self, _now: datetime) -> None:
        """Stop watching a charger that never did what was asked."""
        self._unsubscribe_timer = None
        self._coordinator.async_stop_reboot_watcher()

    @callback
    def _async_unsubscribe(self) -> None:
        """Stop following the charger."""
        if self._unsubscribe_listener is not None:
            self._unsubscribe_listener()
            self._unsubscribe_listener = None
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
            self._unsubscribe_timer = None

    @callback
    def async_stop(self) -> None:
        """Stop watching, however it ended."""
        self._async_unsubscribe()

        # The install is over as far as anyone here can tell, whether the
        # charger came back or ran out of time.
        self._coordinator.install_in_progress = False
        self._coordinator.async_update_listeners()

    @callback
    def _handle_data_coordinator_update(self) -> None:
        """Follow the charger through its reboot."""
        if not self._data_coordinator.last_update_success:
            if self._went_down_at is None:
                # It may have started rebooting, so the shorter allowance
                # applies from here on.
                self._went_down_at = dt_util.utcnow()
                self._async_set_deadline(UPDATE_REBOOT_RETURN_TIMEOUT)
            return

        # Still reachable, so the charger has not started rebooting yet.
        if self._went_down_at is None:
            return

        if dt_util.utcnow() - self._went_down_at < UPDATE_REBOOT_MINIMUM_DOWNTIME:
            # Gone for a moment is the network, not a charger rebooting. Go
            # back to waiting for the reboot to start, on what is left of the
            # original allowance: blips must not keep extending it.
            self._went_down_at = None
            assert self._start_deadline is not None
            self._async_set_deadline(
                max(self._start_deadline - dt_util.utcnow(), timedelta(0))
            )
            return

        # The polls keep coming, so stop following the charger right away
        # rather than leave this to fire a second time.
        self._async_unsubscribe()
        self._entry.async_create_task(
            self._coordinator.hass, self._async_finish(), eager_start=False
        )

    async def _async_finish(self) -> None:
        """Read the new versions before saying the install is done.

        Letting go first would publish "nothing installing" next to the
        versions from before the update, and for as long as the read takes,
        the charger would be offering the package it just took.
        """
        try:
            await self._coordinator.async_request_refresh()
        finally:
            self._coordinator.async_stop_reboot_watcher()


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
