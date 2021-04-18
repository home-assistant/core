"""The Netatmo data handler."""
from __future__ import annotations

from collections import deque
from datetime import timedelta
from functools import partial
from itertools import islice
import logging
from time import time
from typing import Deque

import pyatmo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval

from .const import AUTH, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

CAMERA_DATA_CLASS_NAME = "CameraData"
WEATHERSTATION_DATA_CLASS_NAME = "WeatherStationData"
HOMECOACH_DATA_CLASS_NAME = "HomeCoachData"
HOMEDATA_DATA_CLASS_NAME = "HomeData"
HOMESTATUS_DATA_CLASS_NAME = "HomeStatus"
PUBLICDATA_DATA_CLASS_NAME = "PublicData"

NEXT_SCAN = "next_scan"

DATA_CLASSES = {
    WEATHERSTATION_DATA_CLASS_NAME: pyatmo.WeatherStationData,
    HOMECOACH_DATA_CLASS_NAME: pyatmo.HomeCoachData,
    CAMERA_DATA_CLASS_NAME: pyatmo.CameraData,
    HOMEDATA_DATA_CLASS_NAME: pyatmo.HomeData,
    HOMESTATUS_DATA_CLASS_NAME: pyatmo.HomeStatus,
    PUBLICDATA_DATA_CLASS_NAME: pyatmo.PublicData,
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

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize self."""
        self.hass = hass
        self._auth = hass.data[DOMAIN][entry.entry_id][AUTH]
        self.listeners: list[CALLBACK_TYPE] = []
        self._data_classes: dict = {}
        self.data = {}
        self._queue: Deque = deque()
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
            self._data_classes[data_class["name"]][NEXT_SCAN] = (
                time() + data_class["interval"]
            )

            await self.async_fetch_data(
                data_class["class"], data_class["name"], **data_class["kwargs"]
            )

        self._queue.rotate(BATCH_SIZE)

    @callback
    def async_force_update(self, data_class_entry):
        """Prioritize data retrieval for given data class entry."""
        self._data_classes[data_class_entry][NEXT_SCAN] = time()
        self._queue.rotate(-(self._queue.index(self._data_classes[data_class_entry])))

    async def async_cleanup(self):
        """Clean up the Netatmo data handler."""
        for listener in self.listeners:
            listener()

    async def handle_event(self, event):
        """Handle webhook events."""
        if event["data"]["push_type"] == "webhook_activation":
            _LOGGER.info("%s webhook successfully registered", MANUFACTURER)
            self._webhook = True

        elif event["data"]["push_type"] == "webhook_deactivation":
            _LOGGER.info("%s webhook unregistered", MANUFACTURER)
            self._webhook = False

        elif event["data"]["push_type"] == "NACamera-connection":
            _LOGGER.debug("%s camera reconnected", MANUFACTURER)
            self.async_force_update(CAMERA_DATA_CLASS_NAME)

    async def async_fetch_data(self, data_class, data_class_entry, **kwargs):
        """Fetch data and notify."""
        try:
            self.data[data_class_entry] = await self.hass.async_add_executor_job(
                partial(data_class, **kwargs),
                self._auth,
            )

            for update_callback in self._data_classes[data_class_entry][
                "subscriptions"
            ]:
                if update_callback:
                    update_callback()

        except pyatmo.NoDevice as err:
            _LOGGER.debug(err)
            self.data[data_class_entry] = None

        except pyatmo.ApiError as err:
            _LOGGER.debug(err)

    async def register_data_class(
        self, data_class_name, data_class_entry, update_callback, **kwargs
    ):
        """Register data class."""
        if data_class_entry in self._data_classes:
            self._data_classes[data_class_entry]["subscriptions"].append(
                update_callback
            )
            return

        self._data_classes[data_class_entry] = {
            "class": DATA_CLASSES[data_class_name],
            "name": data_class_entry,
            "interval": DEFAULT_INTERVALS[data_class_name],
            NEXT_SCAN: time() + DEFAULT_INTERVALS[data_class_name],
            "kwargs": kwargs,
            "subscriptions": [update_callback],
        }

        await self.async_fetch_data(
            DATA_CLASSES[data_class_name], data_class_entry, **kwargs
        )

        self._queue.append(self._data_classes[data_class_entry])
        _LOGGER.debug("Data class %s added", data_class_entry)

    async def unregister_data_class(self, data_class_entry, update_callback):
        """Unregister data class."""
        if update_callback not in self._data_classes[data_class_entry]["subscriptions"]:
            return

        self._data_classes[data_class_entry]["subscriptions"].remove(update_callback)

        if not self._data_classes[data_class_entry].get("subscriptions"):
            self._queue.remove(self._data_classes[data_class_entry])
            self._data_classes.pop(data_class_entry)
            _LOGGER.debug("Data class %s removed", data_class_entry)

    @property
    def webhook(self) -> bool:
        """Return the webhook state."""
        return self._webhook
