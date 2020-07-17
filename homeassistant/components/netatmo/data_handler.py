"""The Netatmo data handler."""
import asyncio
from collections import deque
from datetime import timedelta
from functools import partial
from itertools import islice
import logging
from time import time
from typing import Deque, Dict, List

import pyatmo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import AUTH, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


DATA_CLASSES = {
    "WeatherStationData": pyatmo.WeatherStationData,
    "HomeCoachData": pyatmo.HomeCoachData,
    "CameraData": pyatmo.CameraData,
    "HomeData": pyatmo.HomeData,
    "HomeStatus": pyatmo.HomeStatus,
    "PublicData": pyatmo.PublicData,
}

MAX_CALLS_1H = 20
BATCH_SIZE = 3
DEFAULT_INTERVALS = {
    "HomeData": 900,
    "HomeStatus": 300,
    "CameraData": 900,
    "WeatherStationData": 300,
    "HomeCoachData": 300,
    "PublicData": 600,
}
SCAN_INTERVAL = 60


class NetatmoDataHandler:
    """Manages the Netatmo data handling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize self."""
        self.hass = hass
        self._auth = hass.data[DOMAIN][entry.entry_id][AUTH]
        self.listeners: List[CALLBACK_TYPE] = []
        self._data_classes: Dict = {}
        self.data = {}
        self._queue: Deque = deque()
        self._webhook: bool = False

        self.lock = asyncio.Lock()

    async def async_setup(self):
        """Set up the Netatmo data handler."""

        async_track_time_interval(
            self.hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

        self.listeners.append(
            self.hass.bus.async_listen("netatmo_event", self.handle_event)
        )

    async def async_update(self, event_time):
        """Update device."""
        for data_class in islice(self._queue, 0, BATCH_SIZE):
            if data_class["next_scan"] > time():
                continue
            self._data_classes[data_class["name"]]["next_scan"] = (
                time() + data_class["interval"]
            )

            await self.async_fetch_data(
                data_class["class"], data_class["name"], **data_class["kwargs"]
            )

        self._queue.rotate(BATCH_SIZE)

    async def async_cleanup(self):
        """Clean up the Netatmo data handler."""
        for listener in self.listeners:
            listener()

    async def handle_event(self, event):
        """Handle webhook events."""
        if event.data["data"]["push_type"] == "webhook_activation":
            _LOGGER.info("%s webhook successfully registered", MANUFACTURER)
            self._webhook = True

    async def async_fetch_data(self, data_class, data_class_entry, **kwargs):
        """Fetch data and notify."""
        try:
            self.data[data_class_entry] = await self.hass.async_add_executor_job(
                partial(data_class, **kwargs), self._auth,
            )
            async_dispatcher_send(self.hass, f"netatmo-update-{data_class_entry}")
        except (pyatmo.NoDevice, pyatmo.ApiError) as err:
            _LOGGER.debug(err)

    async def register_data_class(self, data_class_name, **kwargs):
        """Register data class."""
        if "home_id" in kwargs:
            data_class_entry = f"{data_class_name}-{kwargs['home_id']}"
        elif "area_name" in kwargs:
            data_class_entry = f"{data_class_name}-{kwargs.pop('area_name')}"
        else:
            data_class_entry = data_class_name

        async with self.lock:
            if data_class_entry not in self._data_classes:
                self._data_classes[data_class_entry] = {
                    "class": DATA_CLASSES[data_class_name],
                    "name": data_class_entry,
                    "interval": DEFAULT_INTERVALS[data_class_name],
                    "next_scan": time() + DEFAULT_INTERVALS[data_class_name],
                    "kwargs": kwargs,
                    "registered": 1,
                }

                await self.async_fetch_data(
                    DATA_CLASSES[data_class_name], data_class_entry, **kwargs
                )

                self._queue.append(self._data_classes[data_class_entry])
                _LOGGER.debug("Data class %s added", data_class_entry)

            else:
                self._data_classes[data_class_entry].update(
                    registered=self._data_classes[data_class_entry]["registered"] + 1
                )

    async def unregister_data_class(self, data_class_entry):
        """Unregister data class."""
        async with self.lock:
            registered = self._data_classes[data_class_entry]["registered"]

            if registered > 1:
                self._data_classes[data_class_entry].update(registered=registered - 1)
            else:
                self._queue.remove(self._data_classes[data_class_entry])
                self._data_classes.pop(data_class_entry)
                _LOGGER.debug("Data class %s removed", data_class_entry)

    @property
    def webhook(self) -> bool:
        """Return the webhook state."""
        return self._webhook


@callback
def add_entities(entities, async_add_entities, hass):
    """Add new sensor entities."""
    async_add_entities(entities)


async def async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, "signal_update")
