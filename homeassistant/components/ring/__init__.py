"""Support for Ring Doorbell/Chimes."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial, wraps
import logging
import time
from typing import Any

from ring_doorbell import (
    Auth,
    AuthenticationError,
    Ring,
    RingError,
    RingEvent,
    RingTimeout,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform, __version__
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util.async_ import run_callback_threadsafe

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = "ring_notification"
NOTIFICATION_TITLE = "Ring Setup"

DOMAIN = "ring"
DEFAULT_ENTITY_NAMESPACE = "ring"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.CAMERA,
    Platform.SIREN,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    def token_updater(token):
        """Handle from sync context when token is updated."""
        run_callback_threadsafe(
            hass.loop,
            partial(
                hass.config_entries.async_update_entry,
                entry,
                data={**entry.data, CONF_ACCESS_TOKEN: token},
            ),
        ).result()

    token = entry.data.get(CONF_ACCESS_TOKEN)
    if token is None:
        raise ConfigEntryAuthFailed()

    auth = Auth(
        f"HomeAssistant/{__version__}", entry.data[CONF_ACCESS_TOKEN], token_updater
    )
    ring = Ring(auth)
    listener_start_timeout = 5
    listener_started_in_time = False
    loop = asyncio.get_running_loop()
    start_listener_func = partial(
        ring.start_event_listener,
        callback_loop=loop,
        listen_loop=loop,
        timeout=listener_start_timeout,
    )

    try:
        await hass.async_add_executor_job(ring.update_data)
        listener_started_in_time = await hass.async_add_executor_job(
            start_listener_func
        )
        if not listener_started_in_time:
            _LOGGER.error(
                "Ring event listener failed to started after %s seconds",
                listener_start_timeout,
            )
    except AuthenticationError as err:
        _LOGGER.warning("Ring access token is no longer valid, need to re-authenticate")
        raise ConfigEntryAuthFailed(err) from err

    active_dings_listener = GlobalDataListener(
        hass,
        "active dings",
        entry,
        ring,
    )
    if listener_started_in_time:
        ring.add_event_listener_callback(active_dings_listener.on_event)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": ring,
        "devices": ring.devices(),
        "listener_started_in_time": listener_started_in_time,
        "device_data": GlobalDataUpdater(
            hass, "device", entry, ring, "update_devices", timedelta(minutes=1)
        ),
        "dings_data": active_dings_listener,
        "history_data": DeviceDataUpdater(
            hass,
            "history",
            entry,
            ring,
            lambda device: device.history(limit=10),
            timedelta(minutes=1),
        ),
        "health_data": DeviceDataUpdater(
            hass,
            "health",
            entry,
            ring,
            lambda device: device.update_health_data(),
            timedelta(minutes=1),
        ),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if hass.services.has_service(DOMAIN, "update"):
        return True

    async def async_refresh_all(_: ServiceCall) -> None:
        """Refresh all ring data."""
        for info in hass.data[DOMAIN].values():
            await info["device_data"].async_refresh_all()
            await hass.async_add_executor_job(info["history_data"].refresh_all)
            await hass.async_add_executor_job(info["health_data"].refresh_all)

    # register service
    hass.services.async_register(DOMAIN, "update", async_refresh_all)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ring entry."""
    ring: Ring = hass.data[DOMAIN][entry.entry_id]["api"]
    ring.stop_event_listener()

    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) != 0:
        return True

    # Last entry unloaded, clean up service
    hass.services.async_remove(DOMAIN, "update")

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        if "token" in new:
            del new["token"]

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


class GlobalDataUpdater:
    """Data storage for single API endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        data_type: str,
        config_entry: ConfigEntry,
        ring: Ring,
        update_method: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize global data updater."""
        self.hass = hass
        self.data_type = data_type
        self.config_entry = config_entry
        self.ring = ring
        self.update_method = update_method
        self.update_interval = update_interval
        self.listeners: list[Callable[[], None]] = []
        self._unsub_interval = None

    @callback
    def async_add_listener(self, update_callback):
        """Listen for data updates."""
        # This is the first listener, set up interval.
        if not self.listeners:
            self._unsub_interval = async_track_time_interval(
                self.hass, self.async_refresh_all, self.update_interval
            )

        self.listeners.append(update_callback)

    @callback
    def async_remove_listener(self, update_callback):
        """Remove data update."""
        self.listeners.remove(update_callback)

        if not self.listeners:
            self._unsub_interval()
            self._unsub_interval = None

    async def async_refresh_all(self, _now: int | None = None) -> None:
        """Time to update."""
        if not self.listeners:
            return

        try:
            await self.hass.async_add_executor_job(
                getattr(self.ring, self.update_method)
            )
        except AuthenticationError:
            _LOGGER.warning(
                "Ring access token is no longer valid, need to re-authenticate"
            )
            self.config_entry.async_start_reauth(self.hass)
            return
        except RingTimeout:
            _LOGGER.warning(
                "Time out fetching Ring %s data",
                self.data_type,
            )
            return
        except RingError as err:
            _LOGGER.error(
                "Error fetching Ring %s data: %s",
                self.data_type,
                err,
            )
            return

        for update_callback in self.listeners:
            update_callback()


class DeviceDataUpdater:
    """Data storage for device data."""

    def __init__(
        self,
        hass: HomeAssistant,
        data_type: str,
        config_entry: ConfigEntry,
        ring: Ring,
        update_method: Callable[[Ring], Any],
        update_interval: timedelta,
    ) -> None:
        """Initialize device data updater."""
        self.data_type = data_type
        self.hass = hass
        self.config_entry = config_entry
        self.ring = ring
        self.update_method = update_method
        self.update_interval = update_interval
        self.devices: dict = {}
        self._unsub_interval = None

    async def async_track_device(self, device, update_callback):
        """Track a device."""
        if not self.devices:
            self._unsub_interval = async_track_time_interval(
                self.hass, self.refresh_all, self.update_interval
            )

        if device.device_id not in self.devices:
            self.devices[device.device_id] = {
                "device": device,
                "update_callbacks": [update_callback],
                "data": None,
            }
            # Store task so that other concurrent requests can wait for us to finish and
            # data be available.
            self.devices[device.device_id]["task"] = asyncio.current_task()
            self.devices[device.device_id][
                "data"
            ] = await self.hass.async_add_executor_job(self.update_method, device)
            self.devices[device.device_id].pop("task")
        else:
            self.devices[device.device_id]["update_callbacks"].append(update_callback)
            # If someone is currently fetching data as part of the initialization, wait for them
            if "task" in self.devices[device.device_id]:
                await self.devices[device.device_id]["task"]

        update_callback(self.devices[device.device_id]["data"])

    @callback
    def async_untrack_device(self, device, update_callback):
        """Untrack a device."""
        self.devices[device.device_id]["update_callbacks"].remove(update_callback)

        if not self.devices[device.device_id]["update_callbacks"]:
            self.devices.pop(device.device_id)

        if not self.devices:
            self._unsub_interval()
            self._unsub_interval = None

    def refresh_all(self, _=None):
        """Refresh all registered devices."""
        for info in self.devices.values():
            try:
                data = info["data"] = self.update_method(info["device"])
            except AuthenticationError:
                _LOGGER.warning(
                    "Ring access token is no longer valid, need to re-authenticate"
                )
                self.config_entry.async_start_reauth(self.hass)
                return
            except RingTimeout:
                _LOGGER.warning(
                    "Time out fetching Ring %s data",
                    self.data_type,
                )
                continue
            except RingError as err:
                _LOGGER.error(
                    "Error fetching Ring %s data: %s",
                    self.data_type,
                    err,
                )
                continue

            for update_callback in info["update_callbacks"]:
                self.hass.loop.call_soon_threadsafe(update_callback, data)


class GlobalDataListener:
    """Data listener for push messages."""

    def __init__(
        self,
        hass: HomeAssistant,
        data_type: str,
        config_entry: ConfigEntry,
        ring: Ring,
    ) -> None:
        """Initialize global data updater."""
        self.hass = hass
        self.data_type = data_type
        self.config_entry = config_entry
        self.ring = ring
        self.listeners: list[Callable[[], None]] = []

    @callback
    def async_add_listener(self, update_callback):
        """Listen for data updates."""
        self.listeners.append(update_callback)

    @callback
    def async_remove_listener(self, update_callback):
        """Remove data update."""
        self.listeners.remove(update_callback)

    def _cb_wrap(self, func):
        @wraps(func)
        def cb_later(_now: datetime) -> None:
            return func()

        return cb_later

    def on_event(self, ring_event: RingEvent) -> None:
        """On a listen event."""
        if not self.listeners:
            return  # pragma: no cover

        _LOGGER.debug("Event received: %s", ring_event)

        start = time.time()

        for update_callback in self.listeners:
            update_callback()
            async_call_later(
                self.hass,
                start - time.time() + ring_event.expires_in,
                self._cb_wrap(update_callback),
            )
