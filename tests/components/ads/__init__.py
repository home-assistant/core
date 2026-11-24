"""Tests for the ADS integration."""

import asyncio
from collections.abc import Callable, Coroutine
import ctypes
from datetime import timedelta
from itertools import count
import threading
from typing import Any

import pyads
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.ads.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import AMS_NET_ID, IP_ADDRESS, PORT

ADS_CONFIG = {"device": AMS_NET_ID, "ip_address": IP_ADDRESS, "port": PORT}

# Entities wait this long for the PLC to deliver a first value.
FIRST_UPDATE_TIMEOUT = timedelta(seconds=10)


def build_notification(handle: int, payload: bytes) -> Any:
    """Build the notification struct the ADS router hands to a callback."""
    header = pyads.structs.SAdsNotificationHeader
    buffer = (ctypes.c_ubyte * (header.data.offset + len(payload)))()
    notification = ctypes.cast(buffer, ctypes.POINTER(header))
    notification.contents.hNotification = handle
    notification.contents.cbSampleSize = len(payload)
    ctypes.memmove(ctypes.addressof(buffer) + header.data.offset, payload, len(payload))
    return notification


class MockAdsDevice:
    """Stand in for the PLC end of the device notifications."""

    def __init__(self) -> None:
        """Initialize the mock device."""
        # Raw bytes delivered when a variable is subscribed to. Variables left
        # out get no first value, as with a PLC that never answers.
        self.values: dict[str, bytes] = {}
        self._handles = count(1)
        self._subscriptions: dict[
            str, list[tuple[int, Callable[[Any, str], None]]]
        ] = {}
        # Threads delivering first values, so tests can wait for them.
        self.deliveries: list[threading.Thread] = []

    def add_device_notification(
        self,
        name: str,
        attr: pyads.NotificationAttrib,
        callback: Callable[[Any, str], None],
    ) -> tuple[int, int]:
        """Hand out a handle, then deliver the first value from another thread."""
        handle = next(self._handles)
        self._subscriptions.setdefault(name, []).append((handle, callback))
        if name in self.values:
            # The hub registers the handle before releasing the lock the
            # callback takes, so the delivery cannot run ahead of it.
            delivery = threading.Thread(
                target=callback,
                args=(build_notification(handle, self.values[name]), name),
                daemon=True,
            )
            self.deliveries.append(delivery)
            delivery.start()
        return handle, handle

    async def async_push(self, hass: HomeAssistant, name: str, payload: bytes) -> None:
        """Deliver a new value to every subscription of a variable, like the router."""
        for handle, callback in self._subscriptions[name]:
            await hass.async_add_executor_job(
                callback, build_notification(handle, payload), name
            )
        await hass.async_block_till_done()

    async def async_push_unknown(self, hass: HomeAssistant, payload: bytes) -> None:
        """Deliver a notification for a handle nobody subscribed to."""
        _, callback = next(iter(self._subscriptions.values()))[0]
        await hass.async_add_executor_job(
            callback, build_notification(next(self._handles), payload), "unknown"
        )


async def setup_ads_platform(
    hass: HomeAssistant, platform: str, platform_config: dict[str, Any]
) -> bool:
    """Set up the ADS connection and one of its entity platforms from YAML."""
    result = await async_setup_component(
        hass,
        platform,
        {DOMAIN: ADS_CONFIG, platform: {"platform": DOMAIN, **platform_config}},
    )
    await hass.async_block_till_done()
    return result


async def async_run_past_first_update(
    hass: HomeAssistant, device: MockAdsDevice, setup: Coroutine[Any, Any, bool]
) -> bool:
    """Run a setup whose entities wait out the first update timeout."""
    task = hass.async_create_task(setup)
    while not task.done():
        # Let the first values arrive before the entities stop waiting for them.
        while any(delivery.is_alive() for delivery in device.deliveries):
            await asyncio.sleep(0.01)
        async_fire_time_changed(hass, dt_util.utcnow() + FIRST_UPDATE_TIMEOUT)
        await asyncio.sleep(0.01)
    return await task
