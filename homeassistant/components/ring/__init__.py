"""Support for Ring Doorbell/Chimes."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from functools import partial
import logging
from typing import Any

import ring_doorbell

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import APPLICATION_NAME, CONF_TOKEN, __version__
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DEVICES_SCAN_INTERVAL,
    DOMAIN,
    HEALTH_SCAN_INTERVAL,
    HISTORY_SCAN_INTERVAL,
    NOTIFICATIONS_SCAN_INTERVAL,
    PLATFORMS,
    RING_API,
    RING_DEVICES,
    RING_DEVICES_COORDINATOR,
    RING_HEALTH_COORDINATOR,
    RING_HISTORY_COORDINATOR,
    RING_NOTIFICATIONS_COORDINATOR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    def token_updater(token):
        """Handle from sync context when token is updated."""
        hass.loop.call_soon_threadsafe(
            partial(
                hass.config_entries.async_update_entry,
                entry,
                data={**entry.data, CONF_TOKEN: token},
            )
        )

    auth = ring_doorbell.Auth(
        f"{APPLICATION_NAME}/{__version__}", entry.data[CONF_TOKEN], token_updater
    )
    ring = ring_doorbell.Ring(auth)

    try:
        await hass.async_add_executor_job(ring.update_data)
    except ring_doorbell.AuthenticationError as err:
        _LOGGER.warning("Ring access token is no longer valid, need to re-authenticate")
        raise ConfigEntryAuthFailed(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        RING_API: ring,
        RING_DEVICES: ring.devices(),
        RING_DEVICES_COORDINATOR: GlobalDataUpdater(
            hass, "device", entry, ring, "update_devices", DEVICES_SCAN_INTERVAL
        ),
        RING_NOTIFICATIONS_COORDINATOR: GlobalDataUpdater(
            hass,
            "active dings",
            entry,
            ring,
            "update_dings",
            NOTIFICATIONS_SCAN_INTERVAL,
        ),
        RING_HISTORY_COORDINATOR: DeviceDataUpdater(
            hass,
            "history",
            entry,
            ring,
            lambda device: device.history(limit=10),
            HISTORY_SCAN_INTERVAL,
        ),
        RING_HEALTH_COORDINATOR: DeviceDataUpdater(
            hass,
            "health",
            entry,
            ring,
            lambda device: device.update_health_data(),
            HEALTH_SCAN_INTERVAL,
        ),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if hass.services.has_service(DOMAIN, "update"):
        return True

    async def async_refresh_all(_: ServiceCall) -> None:
        """Refresh all ring data."""
        for info in hass.data[DOMAIN].values():
            await info["device_data"].async_refresh_all()
            await info["dings_data"].async_refresh_all()
            await hass.async_add_executor_job(info["history_data"].refresh_all)
            await hass.async_add_executor_job(info["health_data"].refresh_all)

    # register service
    hass.services.async_register(DOMAIN, "update", async_refresh_all)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ring entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) != 0:
        return True

    # Last entry unloaded, clean up service
    hass.services.async_remove(DOMAIN, "update")

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
        ring: ring_doorbell.Ring,
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
        except ring_doorbell.AuthenticationError:
            _LOGGER.warning(
                "Ring access token is no longer valid, need to re-authenticate"
            )
            self.config_entry.async_start_reauth(self.hass)
            return
        except ring_doorbell.RingTimeout:
            _LOGGER.warning(
                "Time out fetching Ring %s data",
                self.data_type,
            )
            return
        except ring_doorbell.RingError as err:
            _LOGGER.warning(
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
        ring: ring_doorbell.Ring,
        update_method: Callable[[ring_doorbell.Ring], Any],
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
        for device_id, info in self.devices.items():
            try:
                data = info["data"] = self.update_method(info["device"])
            except ring_doorbell.AuthenticationError:
                _LOGGER.warning(
                    "Ring access token is no longer valid, need to re-authenticate"
                )
                self.hass.loop.call_soon_threadsafe(
                    self.config_entry.async_start_reauth, self.hass
                )
                return
            except ring_doorbell.RingTimeout:
                _LOGGER.warning(
                    "Time out fetching Ring %s data for device %s",
                    self.data_type,
                    device_id,
                )
                continue
            except ring_doorbell.RingError as err:
                _LOGGER.warning(
                    "Error fetching Ring %s data for device %s: %s",
                    self.data_type,
                    device_id,
                    err,
                )
                continue

            for update_callback in info["update_callbacks"]:
                self.hass.loop.call_soon_threadsafe(update_callback, data)
