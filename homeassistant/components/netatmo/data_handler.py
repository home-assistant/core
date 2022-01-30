"""The Netatmo data handler."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import islice
import logging
from time import time
from typing import Any

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
CLIMATE_TOPOLOGY_CLASS_NAME = "AsyncClimateTopology"
CLIMATE_STATE_CLASS_NAME = "AsyncClimate"
PUBLICDATA_DATA_CLASS_NAME = "AsyncPublicData"

DATA_CLASSES = {
    WEATHERSTATION_DATA_CLASS_NAME: pyatmo.AsyncWeatherStationData,
    HOMECOACH_DATA_CLASS_NAME: pyatmo.AsyncHomeCoachData,
    CAMERA_DATA_CLASS_NAME: pyatmo.AsyncCameraData,
    CLIMATE_TOPOLOGY_CLASS_NAME: pyatmo.AsyncClimateTopology,
    CLIMATE_STATE_CLASS_NAME: pyatmo.AsyncClimate,
    PUBLICDATA_DATA_CLASS_NAME: pyatmo.AsyncPublicData,
}

BATCH_SIZE = 3
DEFAULT_INTERVALS = {
    CLIMATE_TOPOLOGY_CLASS_NAME: 3600,
    CLIMATE_STATE_CLASS_NAME: 300,
    CAMERA_DATA_CLASS_NAME: 900,
    WEATHERSTATION_DATA_CLASS_NAME: 600,
    HOMECOACH_DATA_CLASS_NAME: 300,
    PUBLICDATA_DATA_CLASS_NAME: 600,
}
SCAN_INTERVAL = 60


@dataclass
class NetatmoDevice:
    """Netatmo device class."""

    data_handler: NetatmoDataHandler
    device: pyatmo.climate.NetatmoModule
    parent_id: str
    state_class_name: str


@dataclass
class NetatmoDataClass:
    """Class for keeping track of Netatmo data class metadata."""

    name: str
    interval: int
    next_scan: float
    subscriptions: list[CALLBACK_TYPE | None]


class NetatmoDataHandler:
    """Manages the Netatmo data handling."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize self."""
        self.hass = hass
        self.config_entry = config_entry
        self._auth = hass.data[DOMAIN][config_entry.entry_id][AUTH]
        self.data_classes: dict = {}
        self.data: dict = {}
        self._queue: deque = deque()
        self._webhook: bool = False

    async def async_setup(self) -> None:
        """Set up the Netatmo data handler."""

        async_track_time_interval(
            self.hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

        self.config_entry.async_on_unload(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-None",
                self.handle_event,
            )
        )

        await asyncio.gather(
            *[
                self.register_data_class(data_class, data_class, None)
                for data_class in (
                    CLIMATE_TOPOLOGY_CLASS_NAME,
                    CAMERA_DATA_CLASS_NAME,
                    WEATHERSTATION_DATA_CLASS_NAME,
                    HOMECOACH_DATA_CLASS_NAME,
                )
            ]
        )

    async def async_update(self, event_time: datetime) -> None:
        """
        Update device.

        We do up to BATCH_SIZE calls in one update in order
        to minimize the calls on the api service.
        """
        for data_class in islice(self._queue, 0, BATCH_SIZE):
            if data_class.next_scan > time():
                continue

            if data_class_name := data_class.name:
                self.data_classes[data_class_name].next_scan = (
                    time() + data_class.interval
                )

                await self.async_fetch_data(data_class_name)

        self._queue.rotate(BATCH_SIZE)

    @callback
    def async_force_update(self, data_class_entry: str) -> None:
        """Prioritize data retrieval for given data class entry."""
        self.data_classes[data_class_entry].next_scan = time()
        self._queue.rotate(-(self._queue.index(self.data_classes[data_class_entry])))

    async def handle_event(self, event: dict) -> None:
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

    async def async_fetch_data(self, data_class_entry: str) -> None:
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

        for update_callback in self.data_classes[data_class_entry].subscriptions:
            if update_callback:
                update_callback()

    async def register_data_class(
        self,
        data_class_name: str,
        data_class_entry: str,
        update_callback: CALLBACK_TYPE | None,
        **kwargs: Any,
    ) -> None:
        """Register data class."""
        if data_class_entry in self.data_classes:
            if update_callback not in self.data_classes[data_class_entry].subscriptions:
                self.data_classes[data_class_entry].subscriptions.append(
                    update_callback
                )
            return

        self.data_classes[data_class_entry] = NetatmoDataClass(
            name=data_class_entry,
            interval=DEFAULT_INTERVALS[data_class_name],
            next_scan=time() + DEFAULT_INTERVALS[data_class_name],
            subscriptions=[update_callback],
        )

        self.data[data_class_entry] = DATA_CLASSES[data_class_name](
            self._auth, **kwargs
        )

        try:
            await self.async_fetch_data(data_class_entry)
        except KeyError:
            self.data_classes.pop(data_class_entry)
            raise

        self._queue.append(self.data_classes[data_class_entry])
        _LOGGER.debug("Data class %s added", data_class_entry)

    async def unregister_data_class(
        self, data_class_entry: str, update_callback: CALLBACK_TYPE | None
    ) -> None:
        """Unregister data class."""
        self.data_classes[data_class_entry].subscriptions.remove(update_callback)

        if not self.data_classes[data_class_entry].subscriptions:
            self._queue.remove(self.data_classes[data_class_entry])
            self.data_classes.pop(data_class_entry)
            self.data.pop(data_class_entry)
            _LOGGER.debug("Data class %s removed", data_class_entry)

    @property
    def webhook(self) -> bool:
        """Return the webhook state."""
        return self._webhook
