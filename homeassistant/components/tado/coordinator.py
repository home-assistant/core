"""Data update coordinator for Tado integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from PyTado.interface import Tado
from requests import RequestException

from homeassistant.components.climate import PRESET_AWAY, PRESET_HOME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import TadoConfigEntry

from .const import (
    CONF_FALLBACK,
    CONF_REFRESH_TOKEN,
    CONST_OVERLAY_TADO_DEFAULT,
    DOMAIN,
    INSIDE_TEMPERATURE_MEASUREMENT,
    PRESET_AUTO,
    TEMP_OFFSET,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(minutes=5)
SCAN_MOBILE_DEVICE_INTERVAL = timedelta(seconds=30)


class TadoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage API calls from and to Tado via PyTado."""

    tado: Tado
    home_id: int
    home_name: str
    config_entry: TadoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TadoConfigEntry,
        tado: Tado,
        debug: bool = False,
    ) -> None:
        """Initialize the Tado data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._tado = tado
        self._refresh_token = config_entry.data[CONF_REFRESH_TOKEN]
        self._fallback = config_entry.options.get(
            CONF_FALLBACK, CONST_OVERLAY_TADO_DEFAULT
        )
        self._debug = debug

        self.home_id: int
        self.home_name: str
        self.zones: list[dict[Any, Any]] = []
        self.devices: list[dict[Any, Any]] = []
        self.data: dict[str, dict] = {
            "device": {},
            "weather": {},
            "geofence": {},
            "zone": {},
        }
        self._lock = asyncio.Lock()

    @property
    def fallback(self) -> str:
        """Return fallback flag to Smart Schedule."""
        return self._fallback

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch the latest data from Tado."""
        async with self._lock:
            try:
                _LOGGER.debug("Preloading home data")
                tado_home_call = await self.hass.async_add_executor_job(
                    self._tado.get_me
                )
                _LOGGER.debug("Preloading zones and devices")
                self.zones = await self.hass.async_add_executor_job(
                    self._tado.get_zones
                )
                self.devices = await self.hass.async_add_executor_job(
                    self._tado.get_devices
                )
            except RequestException as err:
                raise UpdateFailed(f"Error during Tado setup: {err}") from err

            tado_home = tado_home_call["homes"][0]
            self.home_id = tado_home["id"]
            self.home_name = tado_home["name"]

            devices = await self._async_update_devices()
            zones = await self._async_update_zones()
            home = await self._async_update_home()

            self.data["device"] = devices
            self.data["zone"] = zones
            self.data["weather"] = home["weather"]
            self.data["geofence"] = home["geofence"]

            refresh_token = await self.hass.async_add_executor_job(
                self._tado.get_refresh_token
            )

            if refresh_token != self._refresh_token:
                _LOGGER.debug("New refresh token obtained from Tado: %s", refresh_token)
                self._refresh_token = refresh_token
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_REFRESH_TOKEN: refresh_token},
                )

            return self.data

    async def _async_update_devices(self) -> dict[str, dict]:
        """Fetch the latest data from Tado devices."""
        try:
            devices = await self.hass.async_add_executor_job(self._tado.get_devices)
        except RequestException as err:
            _LOGGER.error("Error updating Tado devices: %s", err)
            raise UpdateFailed(f"Error updating Tado devices: {err}") from err

        if not devices:
            _LOGGER.error("No linked devices found for home ID %s", self.home_id)
            raise UpdateFailed(f"No linked devices found for home ID {self.home_id}")

        return await self.hass.async_add_executor_job(self._update_device_info, devices)

    def _update_device_info(self, devices: list[dict[str, Any]]) -> dict[str, dict]:
        """Update device information."""
        mapped_devices: dict[str, dict] = {}
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
                    device[TEMP_OFFSET] = self._tado.get_device_info(
                        device_short_serial_no, TEMP_OFFSET
                    )
            except RequestException as err:
                _LOGGER.error(
                    "Error updating device %s: %s", device_short_serial_no, err
                )

            _LOGGER.debug(
                "Device %s updated, with data: %s", device_short_serial_no, device
            )
            mapped_devices[device_short_serial_no] = device

        return mapped_devices

    async def _async_update_zones(self) -> dict[int, dict]:
        """Fetch the latest data from Tado zones."""
        try:
            zone_states_call = await self.hass.async_add_executor_job(
                self._tado.get_zone_states
            )
            zone_states = zone_states_call["zoneStates"]
        except RequestException as err:
            _LOGGER.error("Error updating Tado zones: %s", err)
            raise UpdateFailed(f"Error updating Tado zones: {err}") from err

        mapped_zones: dict[int, dict] = {}
        for zone in zone_states:
            mapped_zones[int(zone)] = await self._update_zone(int(zone))

        return mapped_zones

    async def _update_zone(self, zone_id: int) -> dict[str, str]:
        """Update zone information."""
        _LOGGER.debug("Updating zone %s", zone_id)
        try:
            data = await self.hass.async_add_executor_job(
                self._tado.get_zone_state, zone_id
            )
        except RequestException as err:
            _LOGGER.error("Error updating Tado zone %s: %s", zone_id, err)
            raise UpdateFailed(f"Error updating Tado zone {zone_id}: {err}") from err

        _LOGGER.debug("Zone %s updated, with data: %s", zone_id, data)
        return data

    async def _async_update_home(self) -> dict[str, dict]:
        """Fetch the latest data from Tado home."""
        try:
            weather = await self.hass.async_add_executor_job(self._tado.get_weather)
            geofence = await self.hass.async_add_executor_job(self._tado.get_home_state)
        except RequestException as err:
            _LOGGER.error("Error updating Tado home: %s", err)
            raise UpdateFailed(f"Error updating Tado home: {err}") from err

        _LOGGER.debug(
            "Home data updated, with weather and geofence data: %s, %s",
            weather,
            geofence,
        )
        return {"weather": weather, "geofence": geofence}

    async def get_capabilities(self, zone_id: int | str) -> dict:
        """Get capabilities of a zone."""
        try:
            return await self.hass.async_add_executor_job(
                self._tado.get_capabilities, zone_id
            )
        except RequestException as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def get_auto_geofencing_supported(self) -> bool:
        """Check if auto geofencing is supported."""
        try:
            return await self.hass.async_add_executor_job(
                self._tado.get_auto_geofencing_supported
            )
        except RequestException as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def reset_zone_overlay(self, zone_id):
        """Reset the zone overlay."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._tado.reset_zone_overlay, zone_id
                )
                await self._update_zone(zone_id)
            except RequestException as err:
                raise UpdateFailed(f"Error resetting Tado data: {err}") from err

    async def set_presence(self, presence=PRESET_HOME):
        """Set the Tado presence."""
        async with self._lock:
            try:
                if presence == PRESET_AWAY:
                    await self.hass.async_add_executor_job(self._tado.set_away)
                elif presence == PRESET_HOME:
                    await self.hass.async_add_executor_job(self._tado.set_home)
                elif presence == PRESET_AUTO:
                    await self.hass.async_add_executor_job(self._tado.set_auto)
            except RequestException as err:
                raise UpdateFailed(f"Error setting Tado presence: {err}") from err

    async def set_zone_overlay(
        self,
        zone_id=None,
        overlay_mode=None,
        temperature=None,
        duration=None,
        device_type="HEATING",
        mode=None,
        fan_speed=None,
        swing=None,
        fan_level=None,
        vertical_swing=None,
        horizontal_swing=None,
    ) -> None:
        """Set a zone overlay."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._tado.set_zone_overlay,
                    zone_id,
                    overlay_mode,
                    temperature,
                    duration,
                    device_type,
                    "ON",
                    mode,
                    fan_speed,
                    swing,
                    fan_level,
                    vertical_swing,
                    horizontal_swing,
                )
                await self._update_zone(zone_id)
            except RequestException as err:
                raise UpdateFailed(f"Error setting Tado overlay: {err}") from err

    async def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._tado.set_zone_overlay,
                    zone_id,
                    overlay_mode,
                    None,
                    None,
                    device_type,
                    "OFF",
                )
                await self._update_zone(zone_id)
            except RequestException as err:
                raise UpdateFailed(f"Error setting Tado overlay: {err}") from err

    async def set_temperature_offset(self, device_id, offset):
        """Set temperature offset of device."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._tado.set_temp_offset, device_id, offset
                )
            except RequestException as err:
                raise UpdateFailed(
                    f"Error setting Tado temperature offset: {err}"
                ) from err

    async def set_meter_reading(self, reading: int) -> dict[str, Any]:
        """Send meter reading to Tado."""
        async with self._lock:
            dt = datetime.now().strftime("%Y-%m-%d")
            if self._tado is None:
                raise HomeAssistantError("Tado client is not initialized")
            try:
                return await self.hass.async_add_executor_job(
                    self._tado.set_eiq_meter_readings, dt, reading
                )
            except RequestException as err:
                raise UpdateFailed(f"Error setting Tado meter reading: {err}") from err

    async def set_child_lock(self, device_id: str, enabled: bool) -> None:
        """Set child lock of device."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    self._tado.set_child_lock, device_id, enabled
                )
            except RequestException as exc:
                raise HomeAssistantError(
                    f"Error setting Tado child lock: {exc}"
                ) from exc


class TadoMobileDeviceUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage API calls from and to Tado via PyTado for mobile devices."""

    config_entry: TadoConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: TadoConfigEntry, tado: Tado
    ) -> None:
        """Initialize the Tado mobile device update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_MOBILE_DEVICE_INTERVAL,
        )
        self._tado = tado
        self.data: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch the latest data from Tado."""
        async with self._lock:
            try:
                mobile_devices = await self.hass.async_add_executor_job(
                    self._tado.get_mobile_devices
                )
            except RequestException as err:
                _LOGGER.error("Error updating Tado mobile devices: %s", err)
                raise UpdateFailed(
                    f"Error updating Tado mobile devices: {err}"
                ) from err

            mapped_mobile_devices: dict[str, dict] = {}
            for mobile_device in mobile_devices:
                mobile_device_id = mobile_device["id"]
                _LOGGER.debug("Updating mobile device %s", mobile_device_id)
                mapped_mobile_devices[mobile_device_id] = mobile_device

            self.data["mobile_device"] = mapped_mobile_devices
            return self.data
