"""Coordinator for the Philips TV integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ALLOW_NOTIFY, CONF_SYSTEM, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: PhilipsTV, options: Mapping[str, Any]
    ) -> None:
        """Set up the coordinator."""
        self.api = api
        self.options = options
        self._notify_future: asyncio.Task | None = None

        super().__init__(
            hass,
            _LOGGER,
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

        We only run it when TV is considered fully on. When powerstate is in standby, the TV
        will go in low power states and seemingly break the http server in odd ways.
        """
        return (
            self.api.on
            and self.api.powerstate == "On"
            and self.api.notify_change_supported
            and self.options.get(CONF_ALLOW_NOTIFY, False)
        )

    async def _notify_task(self):
        while self._notify_wanted:
            try:
                res = await self.api.notifyChange(130)
            except (ConnectionFailure, AutenticationFailure):
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
    def _unschedule_refresh(self) -> None:
        """Remove data update."""
        super()._unschedule_refresh()
        self._async_notify_stop()

    async def _async_update_data(self):
        """Fetch the latest data from the source."""
        try:
            await self.api.update()
            self._async_notify_schedule()
        except ConnectionFailure:
            pass
        except AutenticationFailure as exception:
            raise ConfigEntryAuthFailed(str(exception)) from exception
        except GeneralFailure as exception:
            raise UpdateFailed(str(exception)) from exception
