"""Library to handle connection with mill."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime as dt
import json
import logging
import time

import aiohttp
import async_timeout

API_ENDPOINT = "https://api.millnorwaycloud.com/"
DEFAULT_TIMEOUT = 10
MIN_TIME_BETWEEN_STATS_UPDATES = dt.timedelta(minutes=10)

_LOGGER = logging.getLogger(__name__)


class Mill:
    """Class to communicate with the Mill api."""

    # pylint: disable=too-many-instance-attributes, too-many-public-methods

    def __init__(self, username, password, timeout=DEFAULT_TIMEOUT, websession=None):
        """Initialize the Mill connection."""
        if websession is None:

            async def _create_session():
                return aiohttp.ClientSession()

            loop = asyncio.get_event_loop()
            self.websession = loop.run_until_complete(_create_session())
        else:
            self.websession = websession
        self._timeout = timeout
        self._username = username
        self._password = password
        self._user_id = None
        self._token = None
        self.heaters = {}
        self.sensors = {}
        self._throttle_time = None
        self._throttle_all_time = None

    async def connect(self, retry=2):
        """Connect to Mill."""
        payload = {"login": self._username, "password": self._password}
        try:
            async with async_timeout.timeout(self._timeout):
                resp = await self.websession.post(
                    API_ENDPOINT + "customer/auth/sign-in",
                    json=payload,
                )
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if retry < 1:
                _LOGGER.error("Error connecting to Mill", exc_info=True)
                return False
            return await self.connect(retry - 1)

        result = await resp.text()
        if "Incorrect login or password" in result:
            _LOGGER.error("Incorrect login or password, %s", result)
            return False
        data = json.loads(result)
        if (token := data.get("idToken")) is None:
            _LOGGER.error("No token")
            return False
        self._token = token

        if self._user_id is not None:
            return True
        async with async_timeout.timeout(self._timeout):
            resp = await self.websession.get(
                API_ENDPOINT + "customer/details",
                headers=self._headers,
            )
        result = await resp.text()
        data = json.loads(result)
        if (user_id := data.get("id")) is None:
            _LOGGER.error("No user id")
            return False
        self._user_id = user_id
        return True

    @property
    def _headers(self):
        return {
            "Authorization": "Bearer " + self._token,
        }

    async def close_connection(self):
        """Close the Mill connection."""
        await self.websession.close()

    async def request(self, command, payload=None, retry=3, patch=False):
        """Request data."""
        if self._token is None:
            _LOGGER.error("No token")
            return None

        _LOGGER.debug("Request %s %s", command, payload)
        url = API_ENDPOINT + command

        try:
            async with async_timeout.timeout(self._timeout):
                if payload:
                    if patch:
                        resp = await self.websession.patch(
                            url, json=payload, headers=self._headers
                        )
                    else:
                        resp = await self.websession.post(
                            url, json=payload, headers=self._headers
                        )
                else:
                    resp = await self.websession.get(url, headers=self._headers)
        except asyncio.TimeoutError:
            if retry < 1:
                _LOGGER.error("Timed out sending command to Mill: %s", url)
                return None
            return await self.request(url, payload, retry - 1)
        except aiohttp.ClientError:
            _LOGGER.error("Error sending command to Mill: %s", url, exc_info=True)
            return None

        result = await resp.text()
        if "InvalidAuthTokenError" in result:
            _LOGGER.error("Invalid auth token, %s", result)
            if await self.connect():
                return await self.request(url, payload, retry - 1)
            return None

        _LOGGER.debug("Result %s", result)
        return json.loads(result)

    async def get_home_list(self):
        """Request data."""
        resp = await self.request("houses")
        if resp is None:
            return []
        return resp.get("ownHouses", [])

    async def update_devices(self):
        """Request data."""
        homes = await self.get_home_list()
        tasks = []
        for home in homes:
            tasks.append(self._update_home(home))
        await asyncio.gather(*tasks)

    async def _update_home(self, home):
        tasks = []
        for room in await self.request(f"houses/{home.get('id')}/devices"):
            tasks.append(self._update_room(home, room))
        await asyncio.gather(*tasks)

    async def _update_room(self, home, room):
        room_data = await self.request(f"rooms/{home.get('id')}/devices")
        print(room_data)

        tasks = []
        for device in room.get("devices", []):
            tasks.append(self._update_device(device, home, room_data))
        await asyncio.gather(*tasks)

    async def _update_device(self, device, home, room_data):
        window_states = {0: "disabled", 3: "enabled_not_active", 2: "enabled_active"}
        device_type = device.get("deviceType", {}).get("parentType", {}).get("name")

        now = dt.datetime.now()

        if device_type in ("Heaters", "Sockets"):
            _id = device.get("deviceId")
            device_stats = await self.request(
                f"devices/{_id}/statistics",
                {"period": "monthly", "year": now.year, "month": 1, "day": 1},
            )
            heater: Heater = self.heaters.get(_id, Heater() if device_type == "Heaters" else Socket())
            if heater.last_updated and (
                now - heater.last_updated < dt.timedelta(seconds=15)
            ):
                return
            heater.name = device.get("customName")
            heater.room_name = device.get("roomName")
            heater.device_id = _id
            heater.available = device.get("isConnected")
            heater.model = (
                device.get("deviceType", {}).get("deviceType", {}).get("name")
            )
            heater.home_id = home.get("houseId")
            heater.set_temp = device.get("lastMetrics").get("temperature")
            heater.current_temp = device.get("lastMetrics").get("temperatureAmbient")
            heater.power_status = device.get("lastMetrics").get("powerStatus", 0) > 0
            heater.open_window = window_states.get(
                device.get("lastMetrics").get("openWindowsStatus")
            )
            heater.day_consumption = device.get("energyUsageForCurrentDay", 0) / 1000.0
            heater.year_consumption = (
                device_stats.get("deviceInfo", {}).get("totalPower", 0) / 1000.0
            )
            heater.room_avg_temp = room_data.get("averageTemperature")
            self.heaters[_id] = heater
        else:
            _LOGGER.error("Unsupported device, %s %s", device_type, device)

    async def set_room_temperatures_by_name(
        self, room_name, sleep_temp=None, comfort_temp=None, away_temp=None
    ):
        """Set room temps by name."""
        if sleep_temp is None and comfort_temp is None and away_temp is None:
            return
        for heater in self.heaters.values():
            if heater.room_name.lower().strip() == room_name.lower().strip():
                await self.set_room_temperatures(
                    room_id, sleep_temp, comfort_temp, away_temp
                )
                return
        _LOGGER.error("Could not find a room with name %s", room_name)

    async def set_room_temperatures(
        self, room_id, sleep_temp=None, comfort_temp=None, away_temp=None
    ):
        """Set room temps."""
        if sleep_temp is None and comfort_temp is None and away_temp is None:
            return
        payload = {}
        if sleep_temp:
            payload["roomSleepTemperature"] = sleep_temp
        if away_temp:
            payload["roomAwayTemperature"] = away_temp
        if comfort_temp:
            payload["roomComfortTemperature"] = comfort_temp

        await self.request(f"rooms/{room_id}/temperature", payload, patch=True)

    async def fetch_heater_data(self):
        """Request data."""
        await self.update_devices()
        return self.heaters

    async def fetch_heater_and_sensor_data(self):
        """Request data."""
        await self.update_devices()
        return {**self.heaters, **self.sensors}

    async def heater_control(self, device_id, power_status):
        """Set heater temps."""
        if device_id not in self.heaters:
            _LOGGER.error("Device id %s not found", device_id)
            return
        payload = {
            "deviceType": "Sockets" if isinstance(self.heaters[device_id], Socket) else "Heaters",
            "enabled": power_status > 0,
            "settings": {
                "operation_mode": "control_individually" if power_status > 0 else "off"
            },
        }
        if await self.request(f"devices/{device_id}/settings", payload, patch=True):
            if power_status > 0:
                self.heaters[device_id].power_status = True
            else:
                self.heaters[device_id].power_status = False
                self.heaters[device_id].is_heating = False
            self.heaters[device_id].last_updated = dt.datetime.now()

    async def set_heater_temp(self, device_id, set_temp):
        """Set heater temp."""
        payload = {
            "deviceType": "Heaters",
            "enabled": True,
            "settings": {
                "operation_mode": "control_individually",
                "temperature_normal": set_temp,
            },
        }
        print("set_heater_temp", set_temp)
        if await self.request(f"devices/{device_id}/settings", payload, patch=True):
            self.heaters[device_id].set_temp = set_temp
            self.heaters[device_id].last_updated = dt.datetime.now()


@dataclass
class MillDevice:
    """Mill Device."""

    name: str | None = None
    device_id: int | None = None
    available: bool | None = None


@dataclass
class Heater(MillDevice):
    """Representation of heater."""

    # pylint: disable=too-many-instance-attributes

    last_updated: dt.datetime | None = None
    model: str | None = None
    home_id: str | None = None
    current_temp: float | None = None
    set_temp: float | None = None
    power_status: bool | None = None
    independent_device: bool | None = True
    open_window: str | None = None
    is_heating: bool | None = None
    day_consumption: float | None = None
    year_consumption: float | None = None
    room_name: str | None = None
    room_avg_temp: float | None = None

@dataclass
class Socket(Heater):

@dataclass
class _SensorAttr:
    """Representation of sensor."""

    # pylint: disable=too-many-instance-attributes
    current_temp: float
    humidity: float
    tvoc: float
    eco2: float
    battery: float
    report_time: int


@dataclass
class Sensor(MillDevice, _SensorAttr):
    """Representation of sensor."""

    @classmethod
    def init_from_response(cls, response):
        """Class method."""
        return cls(
            name=response.get("deviceName"),
            device_id=response.get("deviceId"),
            available=response.get("deviceStatus") == 0,
            current_temp=response.get("currentTemp"),
            humidity=response.get("humidity"),
            tvoc=response.get("tvoc"),
            eco2=response.get("eco2"),
            battery=response.get("batteryPer"),
            report_time=response.get("reportTime"),
        )
