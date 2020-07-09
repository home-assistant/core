"""The Netatmo data handler."""
import asyncio
from datetime import timedelta
from functools import partial
import logging
from time import time
from typing import Dict, List

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
PARALLEL_CALLS = 3
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

    # Central class to manage the polling data from the Netatmo API
    # as well as the push data from the webhook
    #
    # Create one instance of the handler and store it in hass.data
    #
    # Register entities of its platforms when added to HA
    # to receive signals once new data is available
    #
    # Fetch data for all data classes for the first time
    # to gather all available entities
    # then only update periodically the registered data classes and
    # dispatch signals for the registered entities to fetch the new data

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize self."""
        self.hass = hass
        self._auth = hass.data[DOMAIN][entry.entry_id][AUTH]
        self.listeners: List[CALLBACK_TYPE] = []
        self._data_classes: Dict = {}
        self.data = {}
        self._queue: List = []
        self._webhook: bool = False

        self.lock = asyncio.Lock()

    async def async_setup(self):
        """Set up the Netatmo data handler."""

        async def async_update(event_time):
            """Update device."""
            queue = self._queue[0:PARALLEL_CALLS]
            for _ in queue:
                self._queue.append(self._queue.pop(0))

            for data_class in queue:
                if data_class["next_scan"] > time():
                    continue
                self._data_classes[data_class["name"]]["next_scan"] = (
                    time() + data_class["interval"]
                )
                try:
                    self.data[
                        data_class["name"]
                    ] = await self.hass.async_add_executor_job(
                        partial(data_class["class"], **data_class["kwargs"],),
                        self._auth,
                    )
                    async_dispatcher_send(
                        self.hass, f"netatmo-update-{data_class['name']}"
                    )
                except (pyatmo.NoDevice, pyatmo.ApiError) as err:
                    _LOGGER.debug(err)

        async_track_time_interval(
            self.hass, async_update, timedelta(seconds=SCAN_INTERVAL)
        )

        async def handle_event(event):
            """Handle webhook events."""
            if event.data["data"]["push_type"] == "webhook_activation":
                _LOGGER.info("%s webhook successfully registered", MANUFACTURER)
                self._webhook = True

        self.hass.bus.async_listen("netatmo_event", handle_event)

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

                try:
                    self.data[
                        data_class_entry
                    ] = await self.hass.async_add_executor_job(
                        partial(DATA_CLASSES[data_class_name], **kwargs,), self._auth,
                    )
                except (pyatmo.NoDevice, pyatmo.ApiError) as err:
                    _LOGGER.debug(err)

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
