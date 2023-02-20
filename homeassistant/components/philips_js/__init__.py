"""The Philips TV integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from haphilipsjs import AutenticationFailure, ConnectionFailure, PhilipsTV
from haphilipsjs.typing import SystemType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ALLOW_NOTIFY, CONF_SYSTEM, DOMAIN

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.LIGHT,
    Platform.REMOTE,
    Platform.SWITCH,
]

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Philips TV from a config entry."""

    system: SystemType | None = entry.data.get(CONF_SYSTEM)
    tvapi = PhilipsTV(
        entry.data[CONF_HOST],
        entry.data[CONF_API_VERSION],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        system=system,
    )
    coordinator = PhilipsTVDataUpdateCoordinator(hass, tvapi, entry.options)

    await coordinator.async_refresh()

    if (actual_system := tvapi.system) and actual_system != system:
        data = {**entry.data, CONF_SYSTEM: actual_system}
        hass.config_entries.async_update_entry(entry, data=data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=2.0, immediate=False
            ),
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
                LOGGER.debug("Aborting notify due to unexpected return")
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
            raise UpdateFailed(str(exception)) from exception
