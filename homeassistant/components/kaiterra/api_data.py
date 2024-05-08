"""Data for all Kaiterra devices."""
import asyncio
from logging import getLogger

from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError
from kaiterra_async_client import AQIStandard, KaiterraAPIClient, Units

from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_DEVICES, CONF_TYPE
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    AQI_LEVEL,
    AQI_SCALE,
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    DISPATCHER_KAITERRA,
)

_LOGGER = getLogger(__name__)

POLLUTANTS = {"rpm25c": "PM2.5", "rpm10c": "PM10", "rtvoc": "TVOC", "rco2": "CO2"}


class KaiterraApiData:
    """Get data from Kaiterra API."""

    def __init__(self, hass, config, session):
        """Initialize the API data object."""

        api_key = config[CONF_API_KEY]
        aqi_standard = config[CONF_AQI_STANDARD]
        devices = config[CONF_DEVICES]
        units = config[CONF_PREFERRED_UNITS]

        self._hass = hass
        self._api = KaiterraAPIClient(
            session,
            api_key=api_key,
            aqi_standard=AQIStandard.from_str(aqi_standard),
            preferred_units=[Units.from_str(unit) for unit in units],
        )
        self._devices_ids = [device[CONF_DEVICE_ID] for device in devices]
        self._devices = [
            f"/{device[CONF_TYPE]}s/{device[CONF_DEVICE_ID]}" for device in devices
        ]
        self._scale = AQI_SCALE[aqi_standard]
        self._level = AQI_LEVEL[aqi_standard]
        self._update_listeners = []
        self.data = {}

    async def async_update(self) -> None:
        """Get the data from Kaiterra API."""

        try:
            async with asyncio.timeout(10):
                data = await self._api.get_latest_sensor_readings(self._devices)
        except (ClientResponseError, ClientConnectorError, TimeoutError) as err:
            _LOGGER.debug("Couldn't fetch data from Kaiterra API: %s", err)
            self.data = {}
            async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
            return

        _LOGGER.debug("New data retrieved: %s", data)

        try:
            self.data = {}
            for i, device in enumerate(data):
                if not device:
                    self.data[self._devices_ids[i]] = {}
                    continue

                aqi, main_pollutant = None, None
                for sensor_name, sensor in device.items():
                    if not (points := sensor.get("points")):
                        continue

                    point = points[0]
                    sensor["value"] = point.get("value")

                    if "aqi" not in point:
                        continue

                    sensor["aqi"] = point["aqi"]
                    if not aqi or aqi < point["aqi"]:
                        aqi = point["aqi"]
                        main_pollutant = POLLUTANTS.get(sensor_name)

                level = None
                for j in range(1, len(self._scale)):
                    if aqi <= self._scale[j]:
                        level = self._level[j - 1]
                        break

                device["aqi"] = {"value": aqi}
                device["aqi_level"] = {"value": level}
                device["aqi_pollutant"] = {"value": main_pollutant}

                self.data[self._devices_ids[i]] = device
        except IndexError as err:
            _LOGGER.error("Parsing error %s", err)
        except TypeError as err:
            _LOGGER.error("Type error %s", err)

        async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
