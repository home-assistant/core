"""The Netatmo data handler."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import timedelta
from itertools import islice
import logging
from time import time

import pyatmo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    AUTH,
    DOMAIN,
    MANUFACTURER,
    WEBHOOK_ACTIVATION,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_NACAMERA_CONNECTION,
    WEBHOOK_PUSH_TYPE,
)

_LOGGER = logging.getLogger(__name__)

CAMERA_DATA_CLASS_NAME = "AsyncCameraData"
WEATHERSTATION_DATA_CLASS_NAME = "AsyncWeatherStationData"
HOMECOACH_DATA_CLASS_NAME = "AsyncHomeCoachData"
HOMEDATA_DATA_CLASS_NAME = "AsyncHomeData"
HOMESTATUS_DATA_CLASS_NAME = "AsyncHomeStatus"
PUBLICDATA_DATA_CLASS_NAME = "AsyncPublicData"

NEXT_SCAN = "next_scan"

DATA_CLASSES = {
    WEATHERSTATION_DATA_CLASS_NAME: pyatmo.AsyncWeatherStationData,
    HOMECOACH_DATA_CLASS_NAME: pyatmo.AsyncHomeCoachData,
    CAMERA_DATA_CLASS_NAME: pyatmo.AsyncCameraData,
    HOMEDATA_DATA_CLASS_NAME: pyatmo.AsyncHomeData,
    HOMESTATUS_DATA_CLASS_NAME: pyatmo.AsyncHomeStatus,
    PUBLICDATA_DATA_CLASS_NAME: pyatmo.AsyncPublicData,
}

BATCH_SIZE = 3
DEFAULT_INTERVALS = {
    HOMEDATA_DATA_CLASS_NAME: 900,
    HOMESTATUS_DATA_CLASS_NAME: 300,
    CAMERA_DATA_CLASS_NAME: 900,
    WEATHERSTATION_DATA_CLASS_NAME: 600,
    HOMECOACH_DATA_CLASS_NAME: 300,
    PUBLICDATA_DATA_CLASS_NAME: 600,
}
SCAN_INTERVAL = 60


class NetatmoDataHandler:
    """Manages the Netatmo data handling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize self."""
        self.hass = hass
        self._auth = hass.data[DOMAIN][entry.entry_id][AUTH]
        self.listeners: list[CALLBACK_TYPE] = []
        self.data_classes: dict = {}
        self.data = {}
        self._queue = deque()
        self._webhook: bool = False

    async def async_setup(self):
        """Set up the Netatmo data handler."""

        async_track_time_interval(
            self.hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

        self.listeners.append(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-None",
                self.handle_event,
            )
        )

    async def async_update(self, event_time):
        """
        Update device.

        We do up to BATCH_SIZE calls in one update in order
        to minimize the calls on the api service.
        """
        for data_class in islice(self._queue, 0, BATCH_SIZE):
            if data_class[NEXT_SCAN] > time():
                continue

            if data_class_name := data_class["name"]:
                self.data_classes[data_class_name][NEXT_SCAN] = (
                    time() + data_class["interval"]
                )

                await self.async_fetch_data(data_class_name)

        self._queue.rotate(BATCH_SIZE)

    @callback
    def async_force_update(self, data_class_entry):
        """Prioritize data retrieval for given data class entry."""
        self.data_classes[data_class_entry][NEXT_SCAN] = time()
        self._queue.rotate(-(self._queue.index(self.data_classes[data_class_entry])))

    async def async_cleanup(self):
        """Clean up the Netatmo data handler."""
        for listener in self.listeners:
            listener()

    async def handle_event(self, event):
        """Handle webhook events."""
        if event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_ACTIVATION:
            _LOGGER.info("%s webhook successfully registered", MANUFACTURER)
            self._webhook = True

        elif event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_DEACTIVATION:
            _LOGGER.info("%s webhook unregistered", MANUFACTURER)
            self._webhook = False

        elif event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_NACAMERA_CONNECTION:
            _LOGGER.debug("%s camera reconnected", MANUFACTURER)
            self.async_force_update(CAMERA_DATA_CLASS_NAME)

    async def async_fetch_data(self, data_class_entry):
        """Fetch data and notify."""
        if self.data[data_class_entry] is None:
            return

        try:
            await self.data[data_class_entry].async_update()

        except pyatmo.NoDevice as err:
            _LOGGER.debug(err)
            self.data[data_class_entry] = None

        except pyatmo.ApiError as err:
            _LOGGER.debug(err)

        except asyncio.TimeoutError as err:
            _LOGGER.debug(err)
            return

        for update_callback in self.data_classes[data_class_entry]["subscriptions"]:
            if update_callback:
                update_callback()

    async def register_data_class(
        self, data_class_name, data_class_entry, update_callback, **kwargs
    ):
        """Register data class."""
        if data_class_entry in self.data_classes:
            if (
                update_callback
                not in self.data_classes[data_class_entry]["subscriptions"]
            ):
                self.data_classes[data_class_entry]["subscriptions"].append(
                    update_callback
                )
            return

        self.data_classes[data_class_entry] = {
            "name": data_class_entry,
            "interval": DEFAULT_INTERVALS[data_class_name],
            NEXT_SCAN: time() + DEFAULT_INTERVALS[data_class_name],
            "subscriptions": [update_callback],
        }

        self.data[data_class_entry] = DATA_CLASSES[data_class_name](
            self._auth, **kwargs
        )

        await self.async_fetch_data(data_class_entry)

        self._queue.append(self.data_classes[data_class_entry])
        _LOGGER.debug("Data class %s added", data_class_entry)

    async def unregister_data_class(self, data_class_entry, update_callback):
        """Unregister data class."""
        self.data_classes[data_class_entry]["subscriptions"].remove(update_callback)

        if not self.data_classes[data_class_entry].get("subscriptions"):
            self._queue.remove(self.data_classes[data_class_entry])
            self.data_classes.pop(data_class_entry)
            self.data.pop(data_class_entry)
            _LOGGER.debug("Data class %s removed", data_class_entry)

    @property
    def webhook(self) -> bool:
        """Return the webhook state."""
        return self._webhook
