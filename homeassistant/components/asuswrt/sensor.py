"""Asuswrt status sensors."""
from datetime import timedelta
import enum
import logging
from typing import Any, Dict, List, Optional

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.const import DATA_GIGABYTES, DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DATA_ASUSWRT

UPLOAD_ICON = "mdi:upload-network"
DOWNLOAD_ICON = "mdi:download-network"

_LOGGER = logging.getLogger(__name__)


@enum.unique
class _SensorTypes(enum.Enum):
    DEVICES = "devices"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DOWNLOAD_SPEED = "download_speed"
    UPLOAD_SPEED = "upload_speed"

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return a string with the unit of the sensortype."""
        if self in (_SensorTypes.UPLOAD, _SensorTypes.DOWNLOAD):
            return DATA_GIGABYTES
        if self in (_SensorTypes.UPLOAD_SPEED, _SensorTypes.DOWNLOAD_SPEED):
            return DATA_RATE_MEGABITS_PER_SECOND
        return None

    @property
    def icon(self) -> Optional[str]:
        """Return the expected icon for the sensortype."""
        if self in (_SensorTypes.UPLOAD, _SensorTypes.UPLOAD_SPEED):
            return UPLOAD_ICON
        if self in (_SensorTypes.DOWNLOAD, _SensorTypes.DOWNLOAD_SPEED):
            return DOWNLOAD_ICON
        return None

    @property
    def sensor_name(self) -> Optional[str]:
        """Return the name of the sensor."""
        if self is _SensorTypes.DEVICES:
            return "Asuswrt Devices Connected"
        if self is _SensorTypes.UPLOAD:
            return "Asuswrt Upload"
        if self is _SensorTypes.DOWNLOAD:
            return "Asuswrt Download"
        if self is _SensorTypes.UPLOAD_SPEED:
            return "Asuswrt Upload Speed"
        if self is _SensorTypes.DOWNLOAD_SPEED:
            return "Asuswrt Download Speed"
        return None

    @property
    def is_speed(self) -> bool:
        """Return True if the type is an upload/download speed."""
        return self in (_SensorTypes.UPLOAD_SPEED, _SensorTypes.DOWNLOAD_SPEED)

    @property
    def is_size(self) -> bool:
        """Return True if the type is the total upload/download size."""
        return self in (_SensorTypes.UPLOAD, _SensorTypes.DOWNLOAD)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the asuswrt sensors."""
    if discovery_info is None:
        return

    api: AsusWrt = hass.data[DATA_ASUSWRT]

    # Let's discover the valid sensor types.
    sensors = [_SensorTypes(x) for x in discovery_info]

    data_handler = AsuswrtDataHandler(sensors, api)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=data_handler.update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_refresh()
    async_add_entities([AsuswrtSensor(coordinator, x) for x in sensors])


class AsuswrtDataHandler:
    """Class handling the API updates."""

    def __init__(self, sensors: List[_SensorTypes], api: AsusWrt):
        """Initialize the handler class."""
        self._api = api
        self._sensors = sensors
        self._connected = True

    async def update_data(self) -> Dict[_SensorTypes, Any]:
        """Fetch the relevant data from the router."""
        ret_dict: Dict[_SensorTypes, Any] = {}
        try:
            if _SensorTypes.DEVICES in self._sensors:
                # Let's check the nr of devices.
                devices = await self._api.async_get_connected_devices()
                ret_dict[_SensorTypes.DEVICES] = len(devices)

            if any(x.is_speed for x in self._sensors):
                # Let's check the upload and download speed
                speed = await self._api.async_get_current_transfer_rates()
                ret_dict[_SensorTypes.DOWNLOAD_SPEED] = round(speed[0] / 125000, 2)
                ret_dict[_SensorTypes.UPLOAD_SPEED] = round(speed[1] / 125000, 2)

            if any(x.is_size for x in self._sensors):
                rates = await self._api.async_get_bytes_total()
                ret_dict[_SensorTypes.DOWNLOAD] = round(rates[0] / 1000000000, 1)
                ret_dict[_SensorTypes.UPLOAD] = round(rates[1] / 1000000000, 1)

            if not self._connected:
                # Log a successful reconnect
                self._connected = True
                _LOGGER.warning("Successfully reconnected to ASUS router")

        except OSError as err:
            if self._connected:
                # Log the first time connection was lost
                _LOGGER.warning("Lost connection to router error due to: '%s'", err)
                self._connected = False

        return ret_dict


class AsuswrtSensor(CoordinatorEntity):
    """The asuswrt specific sensor class."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_type: _SensorTypes):
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self._type = sensor_type

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._type)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._type.sensor_name

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend."""
        return self._type.icon

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return self._type.unit_of_measurement
