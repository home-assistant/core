"""Flo device object."""
from datetime import datetime, timedelta
import logging
from typing import Any, Callable, Dict, List

from aioflo.api import API

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import SIGNAL_DEVICE_UPDATED, SIGNAL_WATER_CONSUMPTION_UPDATED

_LOGGER = logging.getLogger(__name__)


class FloDevice:
    """Flo device object."""

    def __init__(
        self,
        hass: HomeAssistantType,
        device_information: Dict[str, Any],
        api_client: API,
    ):
        """Initialize the device."""
        self.hass: HomeAssistantType = hass
        self.api_client: API = api_client
        self.unsubs: List[Callable] = []
        self._flo_device_id: str = device_information["id"]
        self._flo_location_id: str = device_information["location"]["id"]
        self._mac_address: str = device_information["macAddress"]
        self._manufacturer: str = "Flo by Moen"
        self._model: str = device_information["deviceModel"]
        self._device_type: str = device_information["deviceType"]
        self._serial_number: str = device_information["serialNumber"]

        self._available: bool = device_information["isConnected"]
        self._firmware_version: str = device_information["fwVersion"]
        self._rssi: int = device_information["connectivity"]["rssi"]
        self._last_heard_from_time: str = device_information["lastHeardFromTime"]
        self._current_system_mode: str = device_information["systemMode"]["lastKnown"]
        self._target_system_mode: str = device_information["systemMode"]["target"]
        self._current_flow_rate: float = device_information["telemetry"]["current"][
            "gpm"
        ]
        self._current_psi: float = device_information["telemetry"]["current"]["psi"]
        self._temperature: float = device_information["telemetry"]["current"]["tempF"]

        self._consumption_today: float = None

        self.unsubs.append(
            async_track_time_interval(
                self.hass, self._update_device, timedelta(seconds=60)
            )
        )
        self.unsubs.append(
            async_track_time_interval(
                self.hass, self.update_consumption_data, timedelta(seconds=60)
            )
        )

    @property
    def location_id(self) -> str:
        """Return Flo location id."""
        return self._flo_location_id

    @property
    def id(self) -> str:
        """Return Flo device id."""
        return self._flo_device_id

    @property
    def name(self) -> str:
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
        self._available = device_information["isConnected"]
        self._firmware_version = device_information["fwVersion"]
        self._rssi = device_information["connectivity"]["rssi"]
        self._last_heard_from_time = device_information["lastHeardFromTime"]
        self._current_system_mode = device_information["systemMode"]["lastKnown"]
        self._target_system_mode = device_information["systemMode"]["target"]
        self._current_flow_rate = device_information["telemetry"]["current"]["gpm"]
        self._current_psi = device_information["telemetry"]["current"]["psi"]
        self._temperature = device_information["telemetry"]["current"]["tempF"]
        self.hass.bus.async_fire(f"{self.mac_address}-{SIGNAL_DEVICE_UPDATED}")

    async def update_consumption_data(self, *_) -> None:
        """Update water consumption data from the API."""
        today = datetime.today()
        start_date = datetime(today.year, today.month, today.day, 0, 0)
        end_date = datetime(today.year, today.month, today.day, 23, 59, 59, 999000)
        water_usage = await self.api_client.water.get_consumption_info(
            self._flo_location_id, start_date, end_date
        )
        _LOGGER.debug("Updated Flo consumption data: %s", water_usage)
        self._consumption_today = water_usage["aggregations"]["sumTotalGallonsConsumed"]
        self.hass.bus.async_fire(
            f"{self.mac_address}-{SIGNAL_WATER_CONSUMPTION_UPDATED}"
        )
