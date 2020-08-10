"""Flo device object."""
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

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
        self._device_information: Optional[Dict[str, Any]] = None
        self._water_usage: Optional[Dict[str, Any]] = None
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
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        return self._manufacturer

    @property
    def mac_address(self) -> str:
        """Return ieee address for device."""
        return self._device_information["macAddress"]

    @property
    def model(self) -> str:
        """Return model for device."""
        return self._device_information["deviceModel"]

    @property
    def rssi(self) -> float:
        """Return rssi for device."""
        return self._device_information["connectivity"]["rssi"]

    @property
    def last_heard_from_time(self) -> str:
        """Return lastHeardFromTime for device."""
        return self._device_information["lastHeardFromTime"]

    @property
    def device_type(self) -> str:
        """Return the device type for the device."""
        return self._device_information["deviceType"]

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.last_update_success and self._device_information["isConnected"]

    @property
    def current_system_mode(self) -> str:
        """Return the current system mode."""
        return self._device_information["systemMode"]["lastKnown"]

    @property
    def target_system_mode(self) -> str:
        """Return the target system mode."""
        return self._device_information["systemMode"]["target"]

    @property
    def current_flow_rate(self) -> float:
        """Return current flow rate in gpm."""
        return self._device_information["telemetry"]["current"]["gpm"]

    @property
    def current_psi(self) -> float:
        """Return the current pressure in psi."""
        return self._device_information["telemetry"]["current"]["psi"]

    @property
    def temperature(self) -> float:
        """Return the current temperature in degrees F."""
        return self._device_information["telemetry"]["current"]["tempF"]

    @property
    def consumption_today(self) -> float:
        """Return the current consumption for today in gallons."""
        return self._water_usage["aggregations"]["sumTotalGallonsConsumed"]

    @property
    def firmware_version(self) -> str:
        """Return the firmware version for the device."""
        return self._device_information["fwVersion"]

    @property
    def serial_number(self) -> str:
        """Return the serial number for the device."""
        return self._device_information["serialNumber"]

    @property
    def pending_info_alerts_count(self) -> int:
        """Return the number of pending info alerts for the device."""
        return self._device_information["notifications"]["pending"]["infoCount"]

    @property
    def pending_warning_alerts_count(self) -> int:
        """Return the number of pending warning alerts for the device."""
        return self._device_information["notifications"]["pending"]["warningCount"]

    @property
    def pending_critical_alerts_count(self) -> int:
        """Return the number of pending critical alerts for the device."""
        return self._device_information["notifications"]["pending"]["criticalCount"]

    @property
    def has_alerts(self) -> bool:
        """Return True if any alert counts are greater than zero."""
        return bool(
            self.pending_info_alerts_count
            or self.pending_warning_alerts_count
            or self.pending_warning_alerts_count
        )

    async def _update_device(self, *_) -> None:
        """Update the device information from the API."""
        self._device_information = await self.api_client.device.get_info(
            self._flo_device_id
        )
        _LOGGER.debug("Flo device data: %s", self._device_information)

    async def _update_consumption_data(self, *_) -> None:
        """Update water consumption data from the API."""
        today = dt_util.now().date()
        start_date = datetime(today.year, today.month, today.day, 0, 0)
        end_date = datetime(today.year, today.month, today.day, 23, 59, 59, 999000)
        self._water_usage = await self.api_client.water.get_consumption_info(
            self._flo_location_id, start_date, end_date
        )
        _LOGGER.debug("Updated Flo consumption data: %s", self._water_usage)
