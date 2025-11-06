"""Coordinator for the Tado integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from tadoasync import Tado, TadoConnectionError, TadoError, TadoReadingError
from tadoasync.models import (
    Capabilities,
    Device,
    HomeState,  # codespell:ignore homestate
    MobileDevice,
    TemperatureOffset,
    Weather,
    Zone,
    ZoneState,
)

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
SCAN_MOBILE_DEVICE_INTERVAL = timedelta(minutes=5)


@dataclass
class TadoDevice:
    """Data structure to hold Tado device data."""

    device: Device
    offset: TemperatureOffset | None = None


@dataclass
class TadoData:
    """Data structure to hold Tado data."""

    devices: dict[str, TadoDevice]
    zones: dict[str, ZoneState]
    weather: Weather
    geofence: HomeState  # codespell:ignore homestate


class TadoDataUpdateCoordinator(DataUpdateCoordinator[TadoData]):
    """Class to manage API calls from and to Tado via PyTado."""

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
        self.zones: dict[str, Zone] = {}

    @property
    def fallback(self) -> str:
        """Return fallback flag to Smart Schedule."""
        return self._fallback

    async def _async_update_data(self) -> TadoData:
        """Fetch the (initial) latest data from Tado."""

        try:
            me = await self._tado.get_me()
            self.zones = {str(zone.id): zone for zone in await self._tado.get_zones()}
            devices = {
                str(device.short_serial_no): TadoDevice(device)
                for device in await self._tado.get_devices()
            }
        except TadoError as err:
            raise UpdateFailed(f"Error during Tado setup: {err}") from err

        home = me.homes[0]
        self.home_id = home.id
        self.home_name = home.name

        await self._async_update_devices(devices)
        zones = await self._async_update_zones()
        weather = await self._tado.get_weather()  # TODO: remove this endpoint
        geofence = await self._tado.get_home_state()

        if self._tado.refresh_token != self._refresh_token:
            _LOGGER.debug(
                "New refresh token obtained from Tado: %s", self._tado.refresh_token
            )
            self._refresh_token = self._tado.refresh_token
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_REFRESH_TOKEN: self._refresh_token,
                },
            )

        return TadoData(devices, zones, weather, geofence)

    async def _async_update_devices(self, devices: dict[str, TadoDevice]) -> None:
        """Update the device data from Tado."""

        if not devices:
            raise UpdateFailed(f"No linked devices found for home ID {self.home_id}")

        for serial_no, device in devices.items():
            _LOGGER.debug("Updating device %s", serial_no)
            if (
                INSIDE_TEMPERATURE_MEASUREMENT
                in device.device.characteristics.capabilities
            ):
                try:
                    offset = await self._tado.get_device_info(serial_no, TEMP_OFFSET)
                except TadoConnectionError as err:
                    _LOGGER.error("Error updating Tado device %s: %s", serial_no, err)
                else:
                    if TYPE_CHECKING:
                        assert isinstance(offset, TemperatureOffset)
                    device.offset = offset

    async def _async_update_zones(self) -> dict[str, ZoneState]:
        """Update the zone data from Tado."""

        try:
            return await self._tado.get_zone_states()
        except TadoConnectionError as err:
            raise UpdateFailed(f"Error updating Tado zones: {err}") from err

    async def _update_zone(self, zone_id: int) -> dict[str, str]:
        """Update the internal data of a zone."""

        _LOGGER.debug("Updating zone %s", zone_id)
        try:
            data = await self._tado.get_zone_state(zone_id)
        except TadoError as err:
            _LOGGER.error("Error updating Tado zone %s: %s", zone_id, err)
            raise UpdateFailed(f"Error updating Tado zone {zone_id}: {err}") from err

        _LOGGER.debug("Zone %s updated, with data: %s", zone_id, data)
        return data

    async def _async_update_home(self) -> dict[str, dict]:
        """Update the home data from Tado."""
        # TODO: this should be removed

        try:
            weather = await self.hass.async_add_executor_job(self._tado.get_weather)
            geofence = await self.hass.async_add_executor_job(self._tado.get_home_state)
        except TadoError as err:
            _LOGGER.error("Error updating Tado home: %s", err)
            raise UpdateFailed(f"Error updating Tado home: {err}") from err

        _LOGGER.debug(
            "Home data updated, with weather and geofence data: %s, %s",
            weather,
            geofence,
        )

        return {"weather": weather, "geofence": geofence}

    async def get_capabilities(self, zone_id: int) -> Capabilities:
        """Fetch the capabilities from Tado."""

        try:
            return await self._tado.get_capabilities(zone_id)
        except TadoConnectionError as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def get_auto_geofencing_supported(self) -> bool:
        """Fetch the auto geofencing supported from Tado."""

        try:
            return (await self._tado.get_auto_geofencing_supported()) or False
        except TadoConnectionError as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def reset_zone_overlay(self, zone_id: int) -> None:
        """Reset the zone back to the default operation."""

        try:
            await self._tado.reset_zone_overlay(zone_id)
        except TadoConnectionError as err:
            raise UpdateFailed(f"Error resetting Tado data: {err}") from err

    async def set_presence(
        self,
        presence: str = PRESET_HOME,
    ) -> None:
        """Set the presence to home, away or auto."""
        mode = {
            PRESET_AWAY: "AWAY",
            PRESET_HOME: "HOME",
            PRESET_AUTO: "AUTO",
        }[presence]

        await self._tado.set_presence(mode)

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

        _LOGGER.debug(
            "Set overlay for zone %s: overlay_mode=%s, temp=%s, duration=%s, type=%s, mode=%s, fan_speed=%s, swing=%s, fan_level=%s, vertical_swing=%s, horizontal_swing=%s",
            zone_id,
            overlay_mode,
            temperature,
            duration,
            device_type,
            mode,
            fan_speed,
            swing,
            fan_level,
            vertical_swing,
            horizontal_swing,
        )

        try:
            await self._tado.set_zone_overlay(
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
        except TadoError as err:
            raise UpdateFailed(f"Error setting Tado overlay: {err}") from err

        await self._update_zone(zone_id)

    async def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        try:
            await self._tado.set_zone_overlay(
                zone_id,
                overlay_mode,
                None,
                None,
                device_type,
                "OFF",
            )
        except TadoError as err:
            raise UpdateFailed(f"Error setting Tado overlay: {err}") from err

        await self._update_zone(zone_id)

    async def set_temperature_offset(self, device_id, offset):
        """Set temperature offset of device."""
        try:
            await self._tado.set_temp_offset(device_id, offset)
        except TadoError as err:
            raise UpdateFailed(f"Error setting Tado temperature offset: {err}") from err

    async def set_meter_reading(self, reading: int) -> None:
        """Send meter reading to Tado."""
        try:
            await self._tado.set_meter_readings(reading)
        except TadoReadingError as err:
            raise HomeAssistantError(
                f"Error setting Tado meter reading: {err}"
            ) from err

    async def set_child_lock(self, device_id: str, enabled: bool) -> None:
        """Set child lock of device."""
        try:
            await self._tado.set_child_lock(device_id, child_lock=enabled)
        except TadoError as exc:
            raise HomeAssistantError(f"Error setting Tado child lock: {exc}") from exc


class TadoMobileDeviceUpdateCoordinator(DataUpdateCoordinator[dict[str, MobileDevice]]):
    """Class to manage the mobile devices from Tado via PyTado."""

    config_entry: TadoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TadoConfigEntry,
        tado: Tado,
    ) -> None:
        """Initialize the Tado data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_MOBILE_DEVICE_INTERVAL,
        )
        self._tado = tado

    async def _async_update_data(self) -> dict[str, MobileDevice]:
        """Fetch the latest data from Tado."""

        try:
            return {
                str(device.id): device
                for device in await self._tado.get_mobile_devices()
            }
        except TadoError as err:
            _LOGGER.error("Error updating Tado mobile devices: %s", err)
            raise UpdateFailed(f"Error updating Tado mobile devices: {err}") from err
