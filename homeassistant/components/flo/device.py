"""Flo device object."""
import asyncio
from datetime import datetime, timedelta
import logging

from aioflo.api import API
from aioflo.errors import RequestError
from async_timeout import timeout

from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN as FLO_DOMAIN

_LOGGER = logging.getLogger(__name__)


class FloDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Flo device object."""

    def __init__(
        self, hass: HomeAssistantType, api_client: API, location_id: str, device_id: str
    ):
        """Initialize the device."""
        self.hass: HomeAssistantType = hass
        self.api_client: API = api_client
        self._flo_location_id: str = location_id
        self._flo_device_id: str = device_id
        self._manufacturer: str = "Flo by Moen"

        self._mac_address: str = None
        self._model: str = None
        self._device_type: str = None
        self._serial_number: str = None
        self._available: bool = None
        self._firmware_version: str = None
        self._rssi: int = None
        self._last_heard_from_time: str = None
        self._current_system_mode: str = None
        self._target_system_mode: str = None
        self._current_flow_rate: float = None
        self._current_psi: float = None
        self._temperature: float = None
        self._consumption_today: float = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{FLO_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            async with timeout(10):
                await asyncio.gather(
                    *[self._update_device(), self._update_consumption_data()]
                )
        except (RequestError) as error:
            raise UpdateFailed(error)

    @property
    def location_id(self) -> str:
        """Return Flo location id."""
        return self._flo_location_id

    @property
    def id(self) -> str:
        """Return Flo device id."""
        return self._flo_device_id

    @property
    def device_name(self) -> str:
        """Return device name."""
        return f"{self.manufacturer} {self.model}"

    @property
    def mac_address(self) -> str:
        """Return ieee address for device."""
        return self._mac_address

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        return self._manufacturer

    @property
    def model(self) -> str:
        """Return model for device."""
        return self._model

    @property
    def rssi(self) -> float:
        """Return rssi for device."""
        return self._rssi

    @property
    def last_heard_from_time(self) -> str:
        """Return lastHeardFromTime for device."""
        return self._last_heard_from_time

    @property
    def device_type(self) -> str:
        """Return the device type for the device."""
        return self._device_type

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @property
    def current_system_mode(self) -> str:
        """Return the current system mode."""
        return self._current_system_mode

    @property
    def target_system_mode(self) -> str:
        """Return the target system mode."""
        return self._target_system_mode

    @property
    def current_flow_rate(self) -> float:
        """Return current flow rate in gpm."""
        return self._current_flow_rate

    @property
    def current_psi(self) -> float:
        """Return the current pressure in psi."""
        return self._current_psi

    @property
    def temperature(self) -> float:
        """Return the current temperature in degrees F."""
        return self._temperature

    @property
    def consumption_today(self) -> float:
        """Return the current consumption for today in gallons."""
        return self._consumption_today

    @property
    def firmware_version(self) -> str:
        """Return the firmware version for the device."""
        return self._firmware_version

    async def _update_device(self, *_) -> None:
        """Update the device information from the API."""
        device_information = await self.api_client.device.get_info(self._flo_device_id)
        _LOGGER.debug("Flo device data: %s", device_information)
        self._mac_address: str = device_information["macAddress"]
        self._model: str = device_information["deviceModel"]
        self._device_type: str = device_information["deviceType"]
        self._serial_number: str = device_information["serialNumber"]
        self._available = device_information["isConnected"]
        self._firmware_version = device_information["fwVersion"]
        self._rssi = device_information["connectivity"]["rssi"]
        self._last_heard_from_time = device_information["lastHeardFromTime"]
        self._current_system_mode = device_information["systemMode"]["lastKnown"]
        self._target_system_mode = device_information["systemMode"]["target"]
        self._current_flow_rate = device_information["telemetry"]["current"]["gpm"]
        self._current_psi = device_information["telemetry"]["current"]["psi"]
        self._temperature = device_information["telemetry"]["current"]["tempF"]

    async def _update_consumption_data(self, *_) -> None:
        """Update water consumption data from the API."""
        today = dt_util.now().date()
        start_date = datetime(today.year, today.month, today.day, 0, 0)
        end_date = datetime(today.year, today.month, today.day, 23, 59, 59, 999000)
        water_usage = await self.api_client.water.get_consumption_info(
            self._flo_location_id, start_date, end_date
        )
        _LOGGER.debug("Updated Flo consumption data: %s", water_usage)
        self._consumption_today = water_usage["aggregations"]["sumTotalGallonsConsumed"]
