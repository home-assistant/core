"""The Netatmo data handler."""
import asyncio
from datetime import timedelta
from functools import partial
import logging
from typing import Dict, List

import pyatmo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import AUTH, DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_CLASSES = {
    "WeatherStationData": pyatmo.WeatherStationData,
    "HomeCoachData": pyatmo.HomeCoachData,
    "CameraData": pyatmo.CameraData,
    "HomeData": pyatmo.HomeData,
    # "HomeStatus": pyatmo.HomeStatus,
}
STATUS_CLASSES = {
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
        self._data_classes: Dict = {}
        self._status_classes: Dict = {}
        self.data = {}
        self._intervals = {}

    async def async_setup(self):
        """Set up a UniFi controller."""
        for data_class in [
            pyatmo.WeatherStationData,
            pyatmo.HomeCoachData,
            pyatmo.CameraData,
            pyatmo.HomeData,
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
                data_results = await asyncio.gather(
                    *[
                        self.hass.async_add_executor_job(
                            partial(
                                self._data_classes[data_class]["class"],
                                # **self._data_classes[data_class]["kwargs"],
                            ),
                            self._auth,
                        )
                        for data_class in self._data_classes
                    ]
                )
            except pyatmo.NoDevice as err:
                _LOGGER.debug(err)

            try:
                status_results = await asyncio.gather(
                    *[
                        self.hass.async_add_executor_job(
                            partial(
                                self._status_classes[data_class]["class"],
                                home_data=self._data_classes["HomeData"]["class"],
                                **self._status_classes[data_class]["kwargs"],
                            ),
                            self._auth,
                        )
                        for data_class in self._status_classes
                    ]
                )
            except pyatmo.NoDevice as err:
                _LOGGER.debug(err)

            for data_class, result in zip(self._data_classes, data_results):
                self.data[data_class] = result
                async_dispatcher_send(self.hass, f"netatmo-update-{data_class}")

            for data_class, result in zip(self._status_classes, status_results):
                self.data[data_class] = result
                async_dispatcher_send(self.hass, f"netatmo-update-{data_class}")

        async_track_time_interval(self.hass, async_update, timedelta(seconds=180))

    async def register_data_class(self, data_class_name, **kwargs):
        """Register data class."""
        if "home_id" in kwargs:
            data_class_entry = f"{data_class_name}-{kwargs['home_id']}"
        else:
            data_class_entry = data_class_name

        if data_class_name in DATA_CLASSES:

            if data_class_entry not in self._data_classes:
                self._data_classes[data_class_entry] = {
                    "class": DATA_CLASSES[data_class_name],
                    "kwargs": kwargs,
                    "registered": 1,
                }
                self.data[data_class_entry] = await self.hass.async_add_executor_job(
                    partial(DATA_CLASSES[data_class_name], **kwargs), self._auth
                )
                _LOGGER.debug("Data class %s added", data_class_name)
            else:
                self._data_classes[data_class_entry].update(
                    registered=self._data_classes[data_class_entry]["registered"] + 1
                )

        elif data_class_name in STATUS_CLASSES:

            if data_class_entry not in self._status_classes:
                self._status_classes[data_class_entry] = {
                    "class": STATUS_CLASSES[data_class_name],
                    "kwargs": kwargs,
                    "registered": 1,
                }
                self.data[data_class_entry] = await self.hass.async_add_executor_job(
                    partial(STATUS_CLASSES[data_class_name], **kwargs), self._auth
                )
                _LOGGER.debug("Status class %s added", data_class_name)
            else:
                self._status_classes[data_class_entry].update(
                    registered=self._status_classes[data_class_entry]["registered"] + 1
                )

    async def unregister_data_class(self, data_class_entry):
        """Unregister data class."""
        if not data_class_entry.startswith("HomeStatus"):
            registered = self._data_classes[data_class_entry]["registered"]
            if registered > 1:
                self._data_classes[data_class_entry].update(registered=registered - 1)
            else:
                self._data_classes.pop(data_class_entry)
                _LOGGER.debug("Data class %s removed", data_class_entry)
        else:
            registered = self._status_classes[data_class_entry]["registered"]
            if registered > 1:
                self._status_classes[data_class_entry].update(registered=registered - 1)
            else:
                self._status_classes.pop(data_class_entry)
                _LOGGER.debug("Status class %s removed", data_class_entry)


@callback
def add_entities(entities, async_add_entities, hass):
    """Add new sensor entities."""
    async_add_entities(entities)


async def async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated."""
    async_dispatcher_send(hass, "signal_update")
