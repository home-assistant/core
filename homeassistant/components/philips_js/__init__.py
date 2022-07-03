"""The Philips TV integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import timedelta
import logging
from typing import Any

from haphilipsjs import ConnectionFailure, PhilipsTV
from haphilipsjs.typing import SystemType

from homeassistant.components.automation import AutomationActionType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import Context, HassJob, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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

    tvapi = PhilipsTV(
        entry.data[CONF_HOST],
        entry.data[CONF_API_VERSION],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )
    coordinator = PhilipsTVDataUpdateCoordinator(hass, tvapi, entry.options)

    await coordinator.async_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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


class PluggableAction:
    """A pluggable action handler."""

    def __init__(self, update: Callable[[], None]) -> None:
        """Initialize."""
        self._update = update
        self._actions: dict[Any, tuple[HassJob, dict[str, Any]]] = {}

    def __bool__(self):
        """Return if we have something attached."""
        return bool(self._actions)

    @callback
    def async_attach(self, action: AutomationActionType, variables: dict[str, Any]):
        """Attach a device trigger for turn on."""

        @callback
        def _remove():
            del self._actions[_remove]
            self._update()

        job = HassJob(action)

        self._actions[_remove] = (job, variables)
        self._update()

        return _remove

    async def async_run(self, hass: HomeAssistant, context: Context | None = None):
        """Run all turn on triggers."""
        for job, variables in self._actions.values():
            hass.async_run_hass_job(job, variables, context)


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    def __init__(self, hass, api: PhilipsTV, options: Mapping) -> None:
        """Set up the coordinator."""
        self.api = api
        self.options = options
        self._notify_future: asyncio.Task | None = None

        self.turn_on = PluggableAction(self.async_update_listeners)

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
        entry: ConfigEntry = self.config_entry
        assert entry
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
            res = await self.api.notifyChange(130)
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

    @callback
    async def _async_update_data(self):
        """Fetch the latest data from the source."""
        try:
            await self.api.update()
            self._async_notify_schedule()
        except ConnectionFailure:
            pass
