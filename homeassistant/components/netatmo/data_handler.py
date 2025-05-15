"""The Netatmo data handler."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import islice
import logging
from time import time
from typing import Any

import aiohttp
import pyatmo
from pyatmo.modules.device_types import (
    DeviceCategory as NetatmoDeviceCategory,
    DeviceType as NetatmoDeviceType,
)
import voluptuous as vol

from homeassistant.components import cloud
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    ATTR_EVENT_TYPE,
    AUTH,
    DATA_PERSONS,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    MANUFACTURER,
    NETATMO_CREATE_BATTERY,
    NETATMO_CREATE_BUTTON,
    NETATMO_CREATE_CAMERA,
    NETATMO_CREATE_CAMERA_LIGHT,
    NETATMO_CREATE_CLIMATE,
    NETATMO_CREATE_COVER,
    NETATMO_CREATE_FAN,
    NETATMO_CREATE_LIGHT,
    NETATMO_CREATE_ROOM_SENSOR,
    NETATMO_CREATE_SELECT,
    NETATMO_CREATE_SENSOR,
    NETATMO_CREATE_SWITCH,
    NETATMO_CREATE_TEMPERATURE_SET,
    NETATMO_CREATE_WEATHER_SENSOR,
    PLATFORMS,
    WEBHOOK_ACTIVATION,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_HOME_EVENT_CHANGED,
    WEBHOOK_NACAMERA_CONNECTION,
    WEBHOOK_PUSH_TYPE,
)

_LOGGER = logging.getLogger(__name__)

SIGNAL_NAME = "signal_name"
ACCOUNT = "account"
HOME = "home"
WEATHER = "weather"
AIR_CARE = "air_care"
PUBLIC = NetatmoDeviceType.public
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
DEV_FACTOR = 7
DEV_LIMIT = 400
CLOUD_FACTOR = 2
CLOUD_LIMIT = 150
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
    _interval_factor: int

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize self."""
        self.hass = hass
        self.config_entry = config_entry
        self._auth = hass.data[DOMAIN][config_entry.entry_id][AUTH]
        self.publisher: dict[str, NetatmoPublisher] = {}
        self._queue: deque = deque()
        self._webhook: bool = False
        if config_entry.data["auth_implementation"] == cloud.DOMAIN:
            self._interval_factor = CLOUD_FACTOR
            self._rate_limit = CLOUD_LIMIT
        else:
            self._interval_factor = DEV_FACTOR
            self._rate_limit = DEV_LIMIT
        self.poll_start = time()
        self.poll_count = 0

    async def async_setup(self) -> None:
        """Set up the Netatmo data handler."""
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
            )
        )

        self.config_entry.async_on_unload(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-None",
                self.handle_event,
            )
        )

        self.config_entry.async_on_unload(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-{EVENT_TYPE_SCHEDULE}",
                self.handle_event,
            )
        )

        self.account = pyatmo.AsyncAccount(self._auth)

        await self.subscribe(ACCOUNT, ACCOUNT, None)

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )
        await self.async_dispatch()

        # Register the sync schedule service
        async_register_admin_service(
            self.hass,
            DOMAIN,
            "sync_schedule",
            self._handle_sync_schedule_service,
            schema=vol.Schema(
                {
                    vol.Required("home_id"): str,
                    vol.Required("schedule_id"): str,
                }
            ),
        )

    async def async_update(self, event_time: datetime) -> None:
        """Update device.

        We do up to BATCH_SIZE calls in one update in order
        to minimize the calls on the api service.
        """
        for data_class in islice(self._queue, 0, BATCH_SIZE * self._interval_factor):
            if data_class.next_scan > time():
                continue

            if publisher := data_class.name:
                error = await self.async_fetch_data(publisher)

                if error:
                    self.publisher[publisher].next_scan = (
                        time() + data_class.interval * 10
                    )
                else:
                    self.publisher[publisher].next_scan = time() + data_class.interval

        self._queue.rotate(BATCH_SIZE)
        cph = self.poll_count / (time() - self.poll_start) * 3600
        _LOGGER.debug("Calls per hour: %i", cph)
        if cph > self._rate_limit:
            for publisher in self.publisher.values():
                publisher.next_scan += 60
        if (time() - self.poll_start) > 3600:
            self.poll_start = time()
            self.poll_count = 0

    @callback
    def async_force_update(self, signal_name: str) -> None:
        """Prioritize data retrieval for given data class entry."""
        self.publisher[signal_name].next_scan = time()
        self._queue.rotate(-(self._queue.index(self.publisher[signal_name])))

    async def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        if event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_ACTIVATION:
            _LOGGER.debug("%s webhook successfully registered", MANUFACTURER)
            self._webhook = True

        elif event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_DEACTIVATION:
            _LOGGER.debug("%s webhook unregistered", MANUFACTURER)
            self._webhook = False

        elif event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_NACAMERA_CONNECTION:
            _LOGGER.debug("%s camera reconnected", MANUFACTURER)
            self.async_force_update(ACCOUNT)

        elif (
            event["data"][WEBHOOK_PUSH_TYPE] == WEBHOOK_HOME_EVENT_CHANGED
            and event["data"][ATTR_EVENT_TYPE] == EVENT_TYPE_SCHEDULE
            and "schedule_id" not in event["data"]
        ):
            _LOGGER.debug("%s schedule updated", MANUFACTURER)
            signal_name = f"{HOME}-{event['data']['home_id']}"
            await self.async_fetch_data(signal_name)
            async_dispatcher_send(self.hass, signal_name)

    async def async_fetch_data(self, signal_name: str) -> bool:
        """Fetch data and notify."""
        self.poll_count += 1
        has_error = False
        try:
            await getattr(self.account, self.publisher[signal_name].method)(
                **self.publisher[signal_name].kwargs
            )

        except (pyatmo.NoDevice, pyatmo.ApiError) as err:
            _LOGGER.debug(err)
            has_error = True

        except (TimeoutError, aiohttp.ClientConnectorError) as err:
            _LOGGER.debug(err)
            return True

        for update_callback in self.publisher[signal_name].subscriptions:
            if update_callback:
                update_callback()

        return has_error

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

        interval = int(DEFAULT_INTERVALS[publisher] / self._interval_factor)
        self.publisher[signal_name] = NetatmoPublisher(
            name=signal_name,
            interval=interval,
            next_scan=time() + interval,
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
            NetatmoDeviceCategory.shutter: [
                NETATMO_CREATE_COVER,
                NETATMO_CREATE_BUTTON,
            ],
            NetatmoDeviceCategory.switch: [
                NETATMO_CREATE_LIGHT,
                NETATMO_CREATE_SWITCH,
                NETATMO_CREATE_SENSOR,
            ],
            NetatmoDeviceCategory.meter: [NETATMO_CREATE_SENSOR],
            NetatmoDeviceCategory.fan: [NETATMO_CREATE_FAN],
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

            # Process temperature sets for each schedule
            for schedule in self.hass.data[DOMAIN][DATA_SCHEDULES][
                home.entity_id
            ].values():
                schedule_id = schedule.entity_id
                schedule_name = schedule.name
                temperature_sets = schedule.zones or []

                for temp_set in temperature_sets:
                    temp_set_id = temp_set.entity_id
                    temp_set_name = temp_set.name

                    rooms = temp_set.rooms

                    # Dispatch a sensor for each room in the temperature set
                    for room in rooms:
                        room_id = room.entity_id
                        # Look up the room in the pyatmo.Home object to get additional attributes
                        full_room = home.rooms.get(room_id)

                        if not full_room:
                            _LOGGER.error(
                                "Room %s not found in home %s", room_id, home.entity_id
                            )
                            continue

                        room_name = full_room.name
                        target_temperature = room.therm_setpoint_temperature

                        async_dispatcher_send(
                            self.hass,
                            NETATMO_CREATE_TEMPERATURE_SET,
                            {
                                "home_id": home.entity_id,
                                "schedule_id": schedule_id,
                                "schedule_name": schedule_name,
                                "temp_set_id": temp_set_id,
                                "temp_set_name": temp_set_name,
                                "room_id": room_id,
                                "room_name": room_name,
                                "therm_setpoint_temperature": target_temperature,
                            },
                            self.update_schedule,  # Pass the update callback
                        )

    def update_schedule(
        self,
        home_id: str,
        schedule_id: str,
        temp_set_id: str,
        room_id: str,
        new_temperature: float,
    ) -> None:
        """Update the schedule with the new temperature."""
        if not (home := self.account.homes.get(home_id)):
            _LOGGER.error("Home %s not found", home_id)
            return

        if not (schedule := home.schedules.get(schedule_id)):
            _LOGGER.error("Schedule %s not found in home %s", schedule_id, home_id)
            return

        # Update the room temperature in the schedule
        for temperature_set in schedule.zones:
            if temperature_set.entity_id == temp_set_id:
                for room in temperature_set.rooms:
                    if room.entity_id == room_id:
                        room.therm_setpoint_temperature = new_temperature
                        _LOGGER.debug(
                            "Updated temperature for room %s in temperature set %s and schedule %s to %s°C",
                            room_id,
                            temp_set_id,
                            schedule_id,
                            new_temperature,
                        )
                        break

    async def sync_schedule(self, home_id: str, schedule_id: str) -> None:
        """Sync the schedule with the Netatmo API."""
        _LOGGER.debug("Syncing schedule %s in home %s", schedule_id, home_id)

        if not (home := self.account.homes.get(home_id)):
            _LOGGER.error("Home %s not found", home_id)
            return

        if not (schedule := home.schedules.get(schedule_id)):
            _LOGGER.error("Schedule %s not found in home %s", schedule_id, home_id)
            return

        await home.async_sync_schedule(schedule_id, schedule)
        _LOGGER.debug(
            "Successfully synced schedule %s in home %s", schedule_id, home_id
        )

    async def _handle_sync_schedule_service(self, call: ServiceCall) -> None:
        """Handle the sync schedule service call."""
        home_id = call.data["home_id"]
        schedule_id = call.data["schedule_id"]

        _LOGGER.debug(
            "Service called to sync schedule %s in home %s", schedule_id, home_id
        )

        try:
            await self.sync_schedule(home_id, schedule_id)
            _LOGGER.debug(
                "Successfully synced schedule %s in home %s", schedule_id, home_id
            )
        except (pyatmo.ApiError, aiohttp.ClientError) as err:
            _LOGGER.error(
                "Failed to sync schedule %s in home %s: %s", schedule_id, home_id, err
            )
