"""The Netatmo data handler."""
import asyncio
from datetime import timedelta
import logging

import pyatmo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import AUTH, DOMAIN

from typing import List, Set  # Any, Awaitable, Callable,; Optional,


_LOGGER = logging.getLogger(__name__)


DATA_CLASSES = {
    "WeatherStationData": pyatmo.WeatherStationData,
    "HomeCoachData": pyatmo.HomeCoachData,
    "CameraData": pyatmo.CameraData,
    "HomeData": pyatmo.HomeData,
    "HomeStatus": pyatmo.HomeStatus,
}


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
        """Initialize the system."""
        self.hass = hass
        self._auth = hass.data[DOMAIN][entry.entry_id][AUTH]
        self.listeners: List[CALLBACK_TYPE] = []
        self._data_classes: Set = set()
        self.data = {}
        self._intervals = {}

    async def async_setup(self):
        """Set up a UniFi controller."""
        for data_class in [
            pyatmo.WeatherStationData,
            pyatmo.HomeCoachData,
            pyatmo.CameraData,
            pyatmo.HomeData,
            pyatmo.HomeStatus,
        ]:
            try:
                self.data[data_class.__name__] = await self.hass.async_add_executor_job(
                    data_class, self._auth
                )
            except pyatmo.NoDevice:
                _LOGGER.debug("No devices for %s", data_class.__name__)
                continue

        async def async_update(event_time):
            """Update device."""
            try:
                results = await asyncio.gather(
                    *[
                        self.hass.async_add_executor_job(data_class, self._auth)
                        for data_class in self._data_classes
                    ]
                )
            except pyatmo.NoDevice as err:
                _LOGGER.debug(err)

            for data_class, result in zip(self._data_classes, results):
                self.data[data_class.__name__] = result
                async_dispatcher_send(
                    self.hass, f"netatmo-update-{data_class.__name__}"
                )

        async_track_time_interval(self.hass, async_update, timedelta(seconds=180))

    def register_device_type(self, device_type):
        """Register data class."""
        if device_type in DATA_CLASSES:
            self._data_classes.add(DATA_CLASSES[device_type])


@callback
def add_entities(entities, async_add_entities, hass):
    """Add new sensor entities."""
    async_add_entities(entities)


async def async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, "signal_update")
