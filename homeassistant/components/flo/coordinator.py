"""Flo device object."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from aioflo.api import API
from aioflo.errors import RequestError
from orjson import JSONDecodeError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN as FLO_DOMAIN, LOGGER


class FloDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Flo device object."""

    _failure_count: int = 0

    def __init__(
        self, hass: HomeAssistant, api_client: API, location_id: str, device_id: str
    ) -> None:
        """Initialize the device."""
        self.hass: HomeAssistant = hass
        self.api_client: API = api_client
        self._flo_location_id: str = location_id
        self._flo_device_id: str = device_id
        self._manufacturer: str = "Flo by Moen"
        self._device_information: dict[str, Any] = {}
        self._water_usage: dict[str, Any] = {}
        super().__init__(
            hass,
            LOGGER,
            name=f"{FLO_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            async with asyncio.timeout(20):
                await self.send_presence_ping()
                await self._update_device()
                await self._update_consumption_data()
                self._failure_count = 0
        except (RequestError, TimeoutError, JSONDecodeError) as error:
            self._failure_count += 1
            if self._failure_count > 3:
                raise UpdateFailed(error) from error

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
        return self._device_information.get(
            "nickname", f"{self.manufacturer} {self.model}"
        )

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
    def humidity(self) -> float:
        """Return the current humidity in percent (0-100)."""
        return self._device_information["telemetry"]["current"]["humidity"]

    @property
    def consumption_today(self) -> float:
        """Return the current consumption for today in gallons."""
        return self._water_usage["aggregations"]["sumTotalGallonsConsumed"]

    @property
    def firmware_version(self) -> str:
        """Return the firmware version for the device."""
        return self._device_information["fwVersion"]

    @property
    def serial_number(self) -> str | None:
        """Return the serial number for the device."""
        return self._device_information.get("serialNumber")

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

    @property
    def water_detected(self) -> bool:
        """Return whether water is detected, for leak detectors."""
        return self._device_information["fwProperties"]["telemetry_water"]

    @property
    def last_known_valve_state(self) -> str:
        """Return the last known valve state for the device."""
        return self._device_information["valve"]["lastKnown"]

    @property
    def target_valve_state(self) -> str:
        """Return the target valve state for the device."""
        return self._device_information["valve"]["target"]

    @property
    def battery_level(self) -> float:
        """Return the battery level for battery-powered device, e.g. leak detectors."""
        return self._device_information["battery"]["level"]

    async def send_presence_ping(self):
        """Send Flo a presence ping."""
        await self.api_client.presence.ping()

    async def async_set_mode_home(self):
        """Set the Flo location to home mode."""
        await self.api_client.location.set_mode_home(self._flo_location_id)

    async def async_set_mode_away(self):
        """Set the Flo location to away mode."""
        await self.api_client.location.set_mode_away(self._flo_location_id)

    async def async_set_mode_sleep(self, sleep_minutes, revert_to_mode):
        """Set the Flo location to sleep mode."""
        await self.api_client.location.set_mode_sleep(
            self._flo_location_id, sleep_minutes, revert_to_mode
        )

    async def async_run_health_test(self):
        """Run a Flo device health test."""
        await self.api_client.device.run_health_test(self._flo_device_id)

    async def _update_device(self, *_) -> None:
        """Update the device information from the API."""
        self._device_information = await self.api_client.device.get_info(
            self._flo_device_id
        )
        LOGGER.debug("Flo device data: %s", self._device_information)

    async def _update_consumption_data(self, *_) -> None:
        """Update water consumption data from the API."""
        today = dt_util.now().date()
        start_date = datetime(today.year, today.month, today.day, 0, 0)
        end_date = datetime(today.year, today.month, today.day, 23, 59, 59, 999000)
        self._water_usage = await self.api_client.water.get_consumption_info(
            self._flo_location_id, start_date, end_date
        )
        LOGGER.debug("Updated Flo consumption data: %s", self._water_usage)
