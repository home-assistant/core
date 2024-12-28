"""Coordinator for the Tado integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import PyTado
import PyTado.exceptions
from PyTado.interface import Tado

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    ConfigEntryError,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, INSIDE_TEMPERATURE_MEASUREMENT, TEMP_OFFSET

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(seconds=30)  # TODO: set back to 5 minutes
SCAN_MOBILE_DEVICE_INTERVAL = timedelta(seconds=30)


class TadoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage API calls from and to Tado via PyTado."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        fallback: str,
        debug: bool = False,
    ) -> None:
        """Initialize the Tado data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.hass = hass
        self._username = username
        self._password = password
        self._fallback = fallback
        self._debug = debug

        self.tado = None
        self.home_id = None
        self.home_name = None
        self.zones: list[dict[Any, Any]] = []
        self.devices: list[dict[Any, Any]] = []
        self.data: dict[str, dict] = {
            "device": {},
            "mobile_device": {},
            "weather": {},
            "geofence": {},
            "zone": {},
        }

    @property
    def fallback(self):
        """Return fallback flag to Smart Schedule."""
        return self._fallback

    async def _async_setup(self):
        """Set up Tado connection and load initial data."""
        try:
            _LOGGER.info("Setting up Tado connection")
            self.tado = await self.hass.async_add_executor_job(
                Tado,
                self._username,
                self._password,
            )
        except PyTado.exceptions.TadoWrongCredentialsException as err:
            raise ConfigEntryError(f"Invalid Tado credentials. Error: {err}") from err
        except PyTado.exceptions.TadoException as err:
            raise UpdateFailed(f"Error during Tado setup: {err}") from err
        _LOGGER.debug("Tado connection established for username: %s", self._username)

        try:
            tado_home_call = await self.hass.async_add_executor_job(self.tado.get_me)
            tado_home = tado_home_call["homes"][0]
            self.home_id = tado_home["id"]
            self.home_name = tado_home["name"]

            _LOGGER.debug("Preloading zones and devices")
            self.zones = await self.hass.async_add_executor_job(self.tado.get_zones)
            self.devices = await self.hass.async_add_executor_job(self.tado.get_devices)
        except Exception as err:
            raise UpdateFailed(f"Error during Tado setup: {err}") from err
        _LOGGER.info("Tado setup complete")

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch the latest data from Tado."""
        try:
            # Fetch updated data for devices, mobile devices, zones, and home
            await self._async_update_devices()
            await self._async_update_mobile_devices()
            await self._async_update_zones()
            await self._async_update_home()
        except Exception as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

        return self.data

    async def _async_update_devices(self) -> None:
        """Update the device data from Tado."""
        try:
            devices = await self.hass.async_add_executor_job(self.tado.get_devices)
        except RuntimeError as err:
            _LOGGER.error("Error updating Tado devices: %s", err)
            raise UpdateFailed(f"Error updating Tado devices: {err}") from err

        if not devices:
            _LOGGER.error("No linked devices found for home ID %s", self.home_id)
            raise UpdateFailed(f"No linked devices found for home ID {self.home_id}")

        for device in devices:
            device_short_serial_no = device["shortSerialNo"]
            _LOGGER.debug("Updating device %s", device_short_serial_no)
            try:
                if (
                    INSIDE_TEMPERATURE_MEASUREMENT
                    in device["characteristics"]["capabilities"]
                ):
                    _LOGGER.debug(
                        "Updating temperature offset for device %s",
                        device_short_serial_no,
                    )
                    device[TEMP_OFFSET] = await self.hass.async_add_executor_job(
                        self.tado.get_device_info, device_short_serial_no, TEMP_OFFSET
                    )
            except RuntimeError:
                _LOGGER.error(
                    "Unable to connect to Tado while updating device %s",
                    device_short_serial_no,
                )
                return

            self.data["device"][device["shortSerialNo"]] = device
            _LOGGER.debug(
                "Device %s updated, with data: %s", device_short_serial_no, device
            )

    async def _async_update_mobile_devices(self) -> None:
        """Update the mobile device(s) data from Tado."""
        try:
            mobile_devices = await self.hass.async_add_executor_job(
                self.tado.get_mobile_devices
            )
        except RuntimeError as err:
            _LOGGER.error("Error updating Tado mobile devices: %s", err)
            raise UpdateFailed(f"Error updating Tado mobile devices: {err}") from err

        if not mobile_devices:
            _LOGGER.error("No linked mobile devices found for home ID %s", self.home_id)
            raise UpdateFailed(
                f"No linked mobile devices found for home ID {self.home_id}"
            )

        for mobile_device in mobile_devices:
            mobile_device_id = mobile_device["id"]
            _LOGGER.debug("Updating mobile device %s", mobile_device_id)
            try:
                self.data["mobile_device"][mobile_device_id] = mobile_device
                _LOGGER.debug(
                    "Mobile device %s updated, with data: %s",
                    mobile_device_id,
                    mobile_device,
                )
            except RuntimeError:
                _LOGGER.error(
                    "Unable to connect to Tado while updating mobile device %s",
                    mobile_device_id,
                )
                return

    async def _async_update_zones(self) -> None:
        """Update the zone data from Tado."""
        try:
            zone_states_call = await self.hass.async_add_executor_job(
                self.tado.get_zone_states
            )
            zone_states = zone_states_call["zoneStates"]
        except RuntimeError as err:
            _LOGGER.error("Error updating Tado zones: %s", err)
            raise UpdateFailed(f"Error updating Tado zones: {err}") from err

        for zone in zone_states:
            await self._update_zone(int(zone))

    async def _update_zone(self, zone_id: int) -> None:
        """Update the internal data of a zone."""
        _LOGGER.debug("Updating zone %s", zone_id)
        try:
            data = await self.hass.async_add_executor_job(
                self.tado.get_zone_state, zone_id
            )
        except RuntimeError as err:
            _LOGGER.error("Error updating Tado zone %s: %s", zone_id, err)
            raise UpdateFailed(f"Error updating Tado zone {zone_id}: {err}") from err

        self.data["zone"][zone_id] = data
        _LOGGER.debug("Zone %s updated, with data: %s", zone_id, data)

    async def _async_update_home(self) -> None:
        """Update the home data from Tado."""
        try:
            self.data["weather"] = await self.hass.async_add_executor_job(
                self.tado.get_weather
            )
            self.data["geofence"] = await self.hass.async_add_executor_job(
                self.tado.get_home_state
            )
        except RuntimeError as err:
            _LOGGER.error("Error updating Tado home: %s", err)
            raise UpdateFailed(f"Error updating Tado home: {err}") from err

        _LOGGER.debug(
            "Home data updated, with weather and geofence data: %s, %s",
            self.data["weather"],
            self.data["geofence"],
        )

    async def async_get_capabilities(self, zone_id) -> dict:
        """Fetch the capabilities from Tado."""
        try:
            return await self.hass.async_add_executor_job(
                self.tado.get_capabilities, zone_id
            )
        except Exception as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def async_get_auto_geofencing_supported(self) -> bool:
        """Fetch the auto geofencing supported from Tado."""
        try:
            return await self.hass.async_add_executor_job(
                self.tado.get_auto_geofencing_supported
            )
        except Exception as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err
