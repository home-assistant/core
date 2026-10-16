"""Coordinator for the Philips TV integration."""

import asyncio
from datetime import timedelta
import logging
import time
from typing import override

from haphilipsjs import (
    AutenticationFailure,
    ConnectionFailure,
    GeneralFailure,
    PhilipsTV,
)
from haphilipsjs.typing import SystemType

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALLOW_NOTIFY,
    CONF_SYSTEM,
    DOMAIN,
    UNREACHABLE_GRACE,
    WAKE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

type PhilipsTVConfigEntry = ConfigEntry[PhilipsTVDataUpdateCoordinator]


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    config_entry: PhilipsTVConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PhilipsTVConfigEntry,
        api: PhilipsTV,
    ) -> None:
        """Set up the coordinator."""
        self.api = api
        self._notify_future: asyncio.Task | None = None
        self._last_seen: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=2.0, immediate=False
            ),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            manufacturer="Philips",
            model=self.system.get("model"),
            name=self.system["name"],
            sw_version=self.system.get("softwareversion"),
        )

    @property
    def system(self) -> SystemType:
        """Return the system descriptor."""
        if self.api.system:
            return self.api.system
        return self.config_entry.data[CONF_SYSTEM]

    @property
    def unique_id(self) -> str:
        """Return the system descriptor."""
        entry = self.config_entry
        if entry.unique_id:
            return entry.unique_id
        assert entry.entry_id
        return entry.entry_id

    @property
    def _notify_wanted(self):
        """Return if the notify feature should be active.

        We only run it when TV is considered fully on.
        When powerstate is in standby, the TV will go in low
        power states and seemingly break the http server in
        odd ways.
        """
        return (
            self.api.on
            and self.api.powerstate == "On"
            and self.api.notify_change_supported
            and self.config_entry.options.get(CONF_ALLOW_NOTIFY, False)
        )

    async def _notify_task(self):
        while self._notify_wanted:
            try:
                res = await self.api.notifyChange(130)
            except ConnectionFailure, AutenticationFailure:
                res = None

            if res:
                self.async_set_updated_data(None)
            elif res is None:
                _LOGGER.debug("Aborting notify due to unexpected return")
                break

    @callback
    def _async_notify_stop(self):
        if self._notify_future:
            self._notify_future.cancel()
            self._notify_future = None

    @callback
    def _async_notify_schedule(self):
        if self._notify_future and not self._notify_future.done():
            return

        if self._notify_wanted:
            self._notify_future = asyncio.create_task(self._notify_task())

    @callback
    @override
    def _unschedule_refresh(self) -> None:
        """Remove data update."""
        super()._unschedule_refresh()
        self._async_notify_stop()

    @property
    def in_grace(self) -> bool:
        """Return if the TV answered recently enough to trust its last state."""
        return (
            self._last_seen is not None
            and time.monotonic() - self._last_seen < UNREACHABLE_GRACE
        )

    @override
    async def _async_update_data(self):
        """Fetch the latest data from the source.

        A TV in standby regularly drops single requests. Instead of marking
        the TV as off after one failed poll, keep the last known state for
        UNREACHABLE_GRACE seconds after the last successful poll. Once that
        has passed, the TV counts as off.
        """
        try:
            await self.api.update()
        except ConnectionFailure:
            pass
        except AutenticationFailure as exception:
            raise ConfigEntryAuthFailed(str(exception)) from exception
        except GeneralFailure as exception:
            _LOGGER.debug("Update failed: %r", exception)
            self.api.on = False

        if self.api.on:
            self._last_seen = time.monotonic()
            self._async_notify_schedule()
        elif self.in_grace and self.api.system:
            # Transient failure: keep the last known state.
            self.api.on = True

    async def async_ensure_reachable(self) -> bool:
        """Wait until the TV answers, for at most WAKE_TIMEOUT seconds."""
        if self.api.on and self.in_grace:
            return True

        deadline = time.monotonic() + WAKE_TIMEOUT
        while True:
            try:
                if await self.api.update():
                    self._last_seen = time.monotonic()
                    return True
            except AutenticationFailure as exception:
                raise ConfigEntryAuthFailed(str(exception)) from exception
            except GeneralFailure as exception:
                _LOGGER.debug("TV not answering yet: %r", exception)
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(2)
