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
from pyatmo.modules.device_types import DeviceCategory as NetatmoDeviceCategory

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    AUTH,
    DATA_PERSONS,
    DATA_SCHEDULES,
    DOMAIN,
    MANUFACTURER,
    NETATMO_CREATE_BATTERY,
    NETATMO_CREATE_CAMERA,
    NETATMO_CREATE_CAMERA_LIGHT,
    NETATMO_CREATE_CLIMATE,
    NETATMO_CREATE_COVER,
    NETATMO_CREATE_LIGHT,
    NETATMO_CREATE_ROOM_SENSOR,
    NETATMO_CREATE_SELECT,
    NETATMO_CREATE_SENSOR,
    NETATMO_CREATE_SWITCH,
    NETATMO_CREATE_WEATHER_SENSOR,
    PLATFORMS,
    WEBHOOK_ACTIVATION,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_NACAMERA_CONNECTION,
    WEBHOOK_PUSH_TYPE,
)

_LOGGER = logging.getLogger(__name__)

SIGNAL_NAME = "signal_name"
ACCOUNT = "account"
HOME = "home"
WEATHER = "weather"
AIR_CARE = "air_care"
PUBLIC = "public"
EVENT = "event"

PUBLISHERS = {
    ACCOUNT: "async_update_topology",
    HOME: "async_update_status",
    WEATHER: "async_update_weather_stations",
    AIR_CARE: "async_update_air_care",
    PUBLIC: "async_update_public_weather",
    EVENT: "async_update_events",
}

BATCH_SIZE = 3
DEFAULT_INTERVALS = {
    ACCOUNT: 10800,
    HOME: 300,
    WEATHER: 600,
    AIR_CARE: 300,
    PUBLIC: 600,
    EVENT: 600,
}
SCAN_INTERVAL = 60


@dataclass
class NetatmoDevice:
    """Netatmo device class."""

    data_handler: NetatmoDataHandler
    device: pyatmo.modules.Module
    parent_id: str
    signal_name: str


@dataclass
class NetatmoHome:
    """Netatmo home class."""

    data_handler: NetatmoDataHandler
    home: pyatmo.Home
    parent_id: str
    signal_name: str


@dataclass
class NetatmoRoom:
    """Netatmo room class."""

    data_handler: NetatmoDataHandler
    room: pyatmo.Room
    parent_id: str
    signal_name: str


@dataclass
class NetatmoPublisher:
    """Class for keeping track of Netatmo data class metadata."""

    name: str
    interval: int
    next_scan: float
    subscriptions: set[CALLBACK_TYPE | None]
    method: str
    kwargs: dict


class NetatmoDataHandler:
    """Manages the Netatmo data handling."""

    account: pyatmo.AsyncAccount

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize self."""
        self.hass = hass
        self.config_entry = config_entry
        self._auth = hass.data[DOMAIN][config_entry.entry_id][AUTH]
        self.publisher: dict[str, NetatmoPublisher] = {}
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

        self.account = pyatmo.AsyncAccount(self._auth)

        await self.subscribe(ACCOUNT, ACCOUNT, None)

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )
        await self.async_dispatch()

    async def async_update(self, event_time: datetime) -> None:
        """
        Update device.

        We do up to BATCH_SIZE calls in one update in order
        to minimize the calls on the api service.
        """
        for data_class in islice(self._queue, 0, BATCH_SIZE):
            if data_class.next_scan > time():
                continue

            if publisher := data_class.name:
                self.publisher[publisher].next_scan = time() + data_class.interval

                await self.async_fetch_data(publisher)

        self._queue.rotate(BATCH_SIZE)

    @callback
    def async_force_update(self, signal_name: str) -> None:
        """Prioritize data retrieval for given data class entry."""
        self.publisher[signal_name].next_scan = time()
        self._queue.rotate(-(self._queue.index(self.publisher[signal_name])))

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
            self.async_force_update(ACCOUNT)

    async def async_fetch_data(self, signal_name: str) -> None:
        """Fetch data and notify."""
        try:
            await getattr(self.account, self.publisher[signal_name].method)(
                **self.publisher[signal_name].kwargs
            )

        except pyatmo.NoDevice as err:
            _LOGGER.debug(err)

        except pyatmo.ApiError as err:
            _LOGGER.debug(err)

        except asyncio.TimeoutError as err:
            _LOGGER.debug(err)
            return

        for update_callback in self.publisher[signal_name].subscriptions:
            if update_callback:
                update_callback()

    async def subscribe(
        self,
        publisher: str,
        signal_name: str,
        update_callback: CALLBACK_TYPE | None,
        **kwargs: Any,
    ) -> None:
        """Subscribe to publisher."""
        if signal_name in self.publisher:
            if update_callback not in self.publisher[signal_name].subscriptions:
                self.publisher[signal_name].subscriptions.add(update_callback)
            return

        if publisher == "public":
            kwargs = {"area_id": self.account.register_public_weather_area(**kwargs)}

        self.publisher[signal_name] = NetatmoPublisher(
            name=signal_name,
            interval=DEFAULT_INTERVALS[publisher],
            next_scan=time() + DEFAULT_INTERVALS[publisher],
            subscriptions={update_callback},
            method=PUBLISHERS[publisher],
            kwargs=kwargs,
        )

        try:
            await self.async_fetch_data(signal_name)
        except KeyError:
            self.publisher.pop(signal_name)
            raise

        self._queue.append(self.publisher[signal_name])
        _LOGGER.debug("Publisher %s added", signal_name)

    async def unsubscribe(
        self, signal_name: str, update_callback: CALLBACK_TYPE | None
    ) -> None:
        """Unsubscribe from publisher."""
        if update_callback not in self.publisher[signal_name].subscriptions:
            return

        self.publisher[signal_name].subscriptions.remove(update_callback)

        if not self.publisher[signal_name].subscriptions:
            self._queue.remove(self.publisher[signal_name])
            self.publisher.pop(signal_name)
            _LOGGER.debug("Publisher %s removed", signal_name)

    @property
    def webhook(self) -> bool:
        """Return the webhook state."""
        return self._webhook

    async def async_dispatch(self) -> None:
        """Dispatch the creation of entities."""
        await self.subscribe(WEATHER, WEATHER, None)
        await self.subscribe(AIR_CARE, AIR_CARE, None)

        self.setup_air_care()

        for home in self.account.homes.values():
            signal_home = f"{HOME}-{home.entity_id}"

            await self.subscribe(HOME, signal_home, None, home_id=home.entity_id)
            await self.subscribe(EVENT, signal_home, None, home_id=home.entity_id)

            self.setup_climate_schedule_select(home, signal_home)
            self.setup_rooms(home, signal_home)
            self.setup_modules(home, signal_home)

            self.hass.data[DOMAIN][DATA_PERSONS][home.entity_id] = {
                person.entity_id: person.pseudo for person in home.persons.values()
            }

        await self.unsubscribe(WEATHER, None)
        await self.unsubscribe(AIR_CARE, None)

    def setup_air_care(self) -> None:
        """Set up home coach/air care modules."""
        for module in self.account.modules.values():
            if module.device_category is NetatmoDeviceCategory.air_care:
                async_dispatcher_send(
                    self.hass,
                    NETATMO_CREATE_WEATHER_SENSOR,
                    NetatmoDevice(
                        self,
                        module,
                        AIR_CARE,
                        AIR_CARE,
                    ),
                )

    def setup_modules(self, home: pyatmo.Home, signal_home: str) -> None:
        """Set up modules."""
        netatmo_type_signal_map = {
            NetatmoDeviceCategory.camera: [
                NETATMO_CREATE_CAMERA,
                NETATMO_CREATE_CAMERA_LIGHT,
            ],
            NetatmoDeviceCategory.dimmer: [NETATMO_CREATE_LIGHT],
            NetatmoDeviceCategory.shutter: [NETATMO_CREATE_COVER],
            NetatmoDeviceCategory.switch: [
                NETATMO_CREATE_LIGHT,
                NETATMO_CREATE_SWITCH,
                NETATMO_CREATE_SENSOR,
            ],
            NetatmoDeviceCategory.meter: [NETATMO_CREATE_SENSOR],
        }
        for module in home.modules.values():
            if not module.device_category:
                continue

            for signal in netatmo_type_signal_map.get(module.device_category, []):
                async_dispatcher_send(
                    self.hass,
                    signal,
                    NetatmoDevice(
                        self,
                        module,
                        home.entity_id,
                        signal_home,
                    ),
                )
            if module.device_category is NetatmoDeviceCategory.weather:
                async_dispatcher_send(
                    self.hass,
                    NETATMO_CREATE_WEATHER_SENSOR,
                    NetatmoDevice(
                        self,
                        module,
                        home.entity_id,
                        WEATHER,
                    ),
                )

    def setup_rooms(self, home: pyatmo.Home, signal_home: str) -> None:
        """Set up rooms."""
        for room in home.rooms.values():
            if NetatmoDeviceCategory.climate in room.features:
                async_dispatcher_send(
                    self.hass,
                    NETATMO_CREATE_CLIMATE,
                    NetatmoRoom(
                        self,
                        room,
                        home.entity_id,
                        signal_home,
                    ),
                )

                for module in room.modules.values():
                    if module.device_category is NetatmoDeviceCategory.climate:
                        async_dispatcher_send(
                            self.hass,
                            NETATMO_CREATE_BATTERY,
                            NetatmoDevice(
                                self,
                                module,
                                room.entity_id,
                                signal_home,
                            ),
                        )

                if "humidity" in room.features:
                    async_dispatcher_send(
                        self.hass,
                        NETATMO_CREATE_ROOM_SENSOR,
                        NetatmoRoom(
                            self,
                            room,
                            room.entity_id,
                            signal_home,
                        ),
                    )

    def setup_climate_schedule_select(
        self, home: pyatmo.Home, signal_home: str
    ) -> None:
        """Set up climate schedule per home."""
        if NetatmoDeviceCategory.climate in [
            next(iter(x)) for x in [room.features for room in home.rooms.values()] if x
        ]:
            self.hass.data[DOMAIN][DATA_SCHEDULES][home.entity_id] = self.account.homes[
                home.entity_id
            ].schedules

            async_dispatcher_send(
                self.hass,
                NETATMO_CREATE_SELECT,
                NetatmoHome(
                    self,
                    home,
                    home.entity_id,
                    signal_home,
                ),
            )
