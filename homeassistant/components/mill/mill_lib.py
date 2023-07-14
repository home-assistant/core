"""Library to handle connection with mill."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime as dt
import json
import logging

import aiohttp
import async_timeout

API_ENDPOINT = "https://api.millnorwaycloud.com/"
DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class Mill:
    """Class to communicate with the Mill api."""

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
        self.devices = {}

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
            if retry < 1:
                _LOGGER.error("Incorrect login or password, %s", result)
                return False
            payload = {
                "login": {
                    "type": "email",
                    "value": self._username,
                },
                "password": self._password,
            }
            async with async_timeout.timeout(self._timeout):
                resp = await self.websession.post(
                    API_ENDPOINT + "cloud-migration/migrate-customer",
                    json=payload,
                )
                _LOGGER.debug("Migrate customer %s", await resp.text())
            await asyncio.sleep(10)
            return await self.connect(retry - 1)
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
            return await self.request(url, payload, retry - 1, patch=patch)
        except aiohttp.ClientError:
            _LOGGER.error("Error sending command to Mill: %s", url, exc_info=True)
            return None

        result = await resp.text()
        if "InvalidAuthTokenError" in result:
            _LOGGER.debug("InvalidAuthTokenError, %s", result)
            await self.connect()
            return await self.request(url, payload, retry - 1, patch=patch)
        if "error" in result:
            raise Exception(result)
        if "InvalidAuthTokenError" in result:
            _LOGGER.error("Invalid auth token, %s", result)
            if await self.connect():
                return await self.request(url, payload, retry - 1)
            return None

        _LOGGER.debug("Result %s", result)
        return json.loads(result)

    async def update_devices(self):
        """Request data."""
        resp = await self.request("houses")
        if resp is None:
            return []
        homes = resp.get("ownHouses", [])
        tasks = []
        for home in homes:
            tasks.append(self._update_home(home))
        await asyncio.gather(*tasks)

    async def _update_home(self, home):
        independent_devices_data = await self.request(
            f"/houses/{home.get('id')}/devices/independent"
        )
        tasks = []
        for device in independent_devices_data.get("items", []):
            tasks.append(self._update_device(device))

        for room in await self.request(f"houses/{home.get('id')}/devices"):
            tasks.append(self._update_room(room))
        await asyncio.gather(*tasks)

    async def _update_room(self, room):
        room_data = await self.request(f"rooms/{room.get('roomId')}/devices")

        tasks = []
        for device in room.get("devices", []):
            tasks.append(self._update_device(device, room_data))
        await asyncio.gather(*tasks)

    async def _update_device(self, device_data, room_data=None):
        window_states = {0: "disabled", 3: "enabled_not_active", 2: "enabled_active"}
        device_type = (
            device_data.get("deviceType", {}).get("parentType", {}).get("name")
        )

        now = dt.datetime.now()

        _id = device_data.get("deviceId")

        if _id in self.devices:
            device = self.devices[_id]
        else:
            if device_type in ("Heaters",):
                device = Heater()
            elif device_type in ("Sensors",):
                device = Sensor()
            elif device_type in ("Sockets",):
                device = Socket()
            else:
                _LOGGER.error("Unsupported device, %s %s", device_type, device_data)
                return

        device.name = device_data.get("customName")
        device.available = device_data.get("isConnected")
        device.device_id = _id
        device.model = (
            device_data.get("deviceType", {}).get("childType", {}).get("name")
        )

        if device_type in ("Sensors",):
            device.current_temp = device_data.get("lastMetrics", {}).get("temperature")
            device.humidity = device_data.get("lastMetrics", {}).get("humidity")
            device.tvoc = device_data.get("lastMetrics", {}).get("tvoc")
            device.eco2 = device_data.get("lastMetrics", {}).get("eco2")
            device.battery = device_data.get("lastMetrics", {}).get("batteryPercentage")
            device.report_time = device_data.get("lastMetrics", {}).get("time")

        elif device_type in ("Heaters", "Sockets"):
            if device.last_updated and (
                now - device.last_updated < dt.timedelta(seconds=15)
            ):
                return
            device_stats = await self.request(
                f"devices/{_id}/statistics",
                {
                    "period": "monthly",
                    "year": now.year,
                    "month": 1,
                    "day": 1,
                },
            )
            device.room_name = device_data.get("roomName")
            device.set_temp = device_data.get("lastMetrics").get("temperature")
            device.current_temp = device_data.get("lastMetrics").get(
                "temperatureAmbient"
            )
            device.power_status = (
                device_data.get("lastMetrics").get("powerStatus", 0) > 0
            )
            device.open_window = window_states.get(
                device_data.get("lastMetrics").get("openWindowsStatus")
            )
            device.day_consumption = (
                device_data.get("energyUsageForCurrentDay", 0) / 1000.0
            )
            device.year_consumption = (
                device_stats.get("deviceInfo", {}).get("totalPower", 0) / 1000.0
            )
            if room_data:
                device.tibber_control = (
                    room_data.get("controlSource", {}).get("tibber") == 1
                )
                device.home_id = room_data.get("houseId")
                device.room_id = room_data.get("id")
                device.room_avg_temp = room_data.get("averageTemperature")
                device.independent_device = False
            else:
                device.independent_device = True

        self.devices[_id] = device

    async def set_room_temperatures_by_name(
        self, room_name, sleep_temp=None, comfort_temp=None, away_temp=None
    ):
        """Set room temps by name."""
        if sleep_temp is None and comfort_temp is None and away_temp is None:
            return
        for heater in self.devices.values():
            if heater.room_name.lower().strip() == room_name.lower().strip():
                await self.set_room_temperatures(
                    heater.room_id,
                    sleep_temp,
                    comfort_temp,
                    away_temp,
                )
                return
        _LOGGER.error("Could not find a room with name %s", room_name)

    async def set_room_temperatures(
        self,
        room_id,
        sleep_temp=None,
        comfort_temp=None,
        away_temp=None,
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
        return {
            key: val
            for key, val in self.devices.items()
            if isinstance(val, Heater) or isinstance(val, Socket)
        }

    async def fetch_heater_and_sensor_data(self):
        """Request data."""
        await self.update_devices()
        return self.devices

    async def heater_control(self, device_id, power_status):
        """Set heater temps."""
        if device_id not in self.devices:
            _LOGGER.error("Device id %s not found", device_id)
            return
        payload = {
            "deviceType": self._find_device_type(device_id),
            "enabled": power_status > 0,
            "settings": {
                "operation_mode": "control_individually" if power_status > 0 else "off"
            },
        }
        if await self.request(f"devices/{device_id}/settings", payload, patch=True):
            if power_status > 0:
                self.devices[device_id].power_status = True
            else:
                self.devices[device_id].power_status = False
                self.devices[device_id].is_heating = False
            self.devices[device_id].last_updated = dt.datetime.now()

    async def set_heater_temp(self, device_id, set_temp):
        """Set heater temp."""
        payload = {
            "deviceType": self._find_device_type(device_id),
            "enabled": True,
            "settings": {
                "operation_mode": "control_individually",
                "temperature_normal": set_temp,
            },
        }
        if await self.request(f"devices/{device_id}/settings", payload, patch=True):
            self.devices[device_id].set_temp = set_temp
            self.devices[device_id].last_updated = dt.datetime.now()

    def _find_device_type(self, device_id):
        """Find device type."""
        if device_id not in self.devices:
            _LOGGER.error("Device id %s not found", device_id)
            return
        if isinstance(self.devices[device_id], Socket):
            return "Sockets"
        if isinstance(self.devices[device_id], Heater):
            return "Heaters"
        if isinstance(self.devices[device_id], Sensor):
            return "Sensors"
        _LOGGER.error("Unknown device type %s", self.devices[device_id])


@dataclass
class MillDevice:
    """Mill Device."""

    name: str | None = None
    device_id: int | None = None
    available: bool | None = None
    model: str | None = None


@dataclass
class Heater(MillDevice):
    """Representation of heater."""

    # pylint: disable=too-many-instance-attributes

    last_updated: dt.datetime | None = None
    home_id: str | None = None
    room_id: str | None = None
    current_temp: float | None = None
    set_temp: float | None = None
    power_status: bool | None = None
    independent_device: bool | None = None
    open_window: str | None = None
    is_heating: bool | None = None
    tibber_control: bool | None = None
    day_consumption: float | None = None
    year_consumption: float | None = None
    room_name: str | None = None
    room_avg_temp: float | None = None


@dataclass
class Socket(Heater):
    pass


@dataclass
class Sensor(MillDevice):
    """Representation of sensor."""

    current_temp: float | None = None
    humidity: float | None = None
    tvoc: float | None = None
    eco2: float | None = None
    battery: float | None = None
    report_time: int | None = None
