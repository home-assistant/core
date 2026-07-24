"""Coordinator for the Tado integration."""

from datetime import datetime, time, timedelta
import logging
from typing import Any, override
from zoneinfo import ZoneInfo

from PyTado.interface import Tado
from PyTado.interface.api.my_tado import Timetable
from PyTado.zone import TadoZone
from requests import RequestException

from homeassistant.components.climate import PRESET_AWAY, PRESET_HOME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FALLBACK,
    CONF_REFRESH_TOKEN,
    CONST_OVERLAY_TADO_DEFAULT,
    DOMAIN,
    INSIDE_TEMPERATURE_MEASUREMENT,
    PRESET_AUTO,
    TEMP_OFFSET,
    TIMETABLE_TRANSLATION_KEY,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(minutes=5)

type TadoConfigEntry = ConfigEntry[TadoDataUpdateCoordinator]


class TadoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        self.data: dict[str, Any] = {
            "device": {},
            "weather": {},
            "geofence": {},
            "timetable": {},
            "zone": {},
        }

        self._current_interval: float = 0
        self._next_update: datetime | None = None
        self._time_until_reset: float = 0

    @property
    def fallback(self) -> str:
        """Return fallback flag to Smart Schedule."""
        return self._fallback

    @property
    def _enabled_timetable_zone_ids(self) -> set[int]:
        """Return the zone IDs whose timetable select entity is enabled."""
        registry = er.async_get(self.hass)
        return {
            int(entry.unique_id.split(" ")[0])
            for entry in er.async_entries_for_config_entry(
                registry, self.config_entry.entry_id
            )
            if entry.translation_key == TIMETABLE_TRANSLATION_KEY
            and entry.disabled_by is None
        }

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the (initial) latest data from Tado."""

        def _load_tado_data() -> tuple[dict, list, list]:
            """Load Tado data in one call."""
            _LOGGER.debug("Preloading Tado data")
            return (
                self._tado.get_me(),
                self._tado.get_zones(),
                self._tado.get_devices(),
            )

        try:
            (
                tado_home_call,
                self.zones,
                self.devices,
            ) = await self.hass.async_add_executor_job(_load_tado_data)
        except RequestException as err:
            _LOGGER.debug("Checking rate limit")
            ratelimit = self.get_rate_limit()
            if ratelimit.get("remaining") == "0":
                raise UpdateFailed(f"Tado API rate limit reached: {err}") from err
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

        enabled_timetable_zones = self._enabled_timetable_zone_ids
        if enabled_timetable_zones:
            self.data["timetable"] = await self._async_update_timetables(
                enabled_timetable_zones
            )

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

        # Calculate the most recent update interval
        self._calculate_update_interval(len(enabled_timetable_zones))

        return self.data

    @property
    def _is_any_zone_active(self) -> bool:
        """Check if any zone is currently active (heating or AC running)."""
        return any(
            (
                zone_data.heating_power_percentage is not None
                and zone_data.heating_power_percentage > 0
            )
            or zone_data.ac_power == "ON"
            for zone_data in self.data.get("zone", {}).values()
        )

    def _calculate_update_interval(self, timetable_zone_count: int) -> None:
        """Calculate an update interval based on remaining calls and estimates."""

        # Tado resets somewhere between 12:00 and 13:00, Berlin time
        # So let's pretend we're in Berlin...
        reset_time = dt_util.now(ZoneInfo("Europe/Berlin"))

        today_reset = datetime.combine(
            reset_time.date(),
            time(hour=12, minute=0),
            tzinfo=ZoneInfo("Europe/Berlin"),
        )

        next_reset = today_reset
        if reset_time >= today_reset:
            next_reset = today_reset + timedelta(days=1)

        self._time_until_reset = (next_reset - reset_time).total_seconds()

        # When any zone is actively heating, we use a shorter minimum
        # To prevent overshooting in temperature,
        # check if there's heating/cooling activity
        # Accept five minutes to "overshoot", else reset back to 30 minutes
        min_interval = 300 if self._is_any_zone_active else 1800

        remaining_calls = int(self.data.get("rate_limit", {}).get("remaining", 0))
        if remaining_calls is None or remaining_calls <= 0:
            # If rate limit info is unavailable, fall back to the static interval.
            self._current_interval = SCAN_INTERVAL.total_seconds()
            self.update_interval = SCAN_INTERVAL
            self._next_update = reset_time + timedelta(seconds=self._current_interval)
            _LOGGER.debug(
                "Rate limit info unavailable;"
                " using default update interval: %s seconds",
                self._current_interval,
            )
            return

        # Each refresh cycle costs 9 + len(zones) calls (zone state per zone),
        # plus one extra call per zone whose timetable entity is enabled.
        # Also take 10% of the remaining calls as buffer.
        self._current_interval = max(
            min_interval,
            (self._time_until_reset * (9 + len(self.zones) + timetable_zone_count))
            / (remaining_calls * 0.9),
        )

        self._next_update = reset_time + timedelta(seconds=self._current_interval)
        self.update_interval = timedelta(seconds=self._current_interval)

        _LOGGER.debug(
            "Calculated new update interval: %s seconds, for remaining calls: %s",
            self._current_interval,
            remaining_calls,
        )

    async def _async_update_devices(self) -> dict[str, dict]:
        """Update the device data from Tado."""

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
        """Update the device data from Tado."""
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

    async def _async_update_zones(self) -> dict[int, TadoZone]:
        """Update the zone data from Tado."""

        try:
            zone_states_call = await self.hass.async_add_executor_job(
                self._tado.get_zone_states
            )
            zone_states = zone_states_call["zoneStates"]
        except RequestException as err:
            _LOGGER.error("Error updating Tado zones: %s", err)
            raise UpdateFailed(f"Error updating Tado zones: {err}") from err

        mapped_zones: dict[int, TadoZone] = {}
        for zone_id_str, raw_state in zone_states.items():
            zone_id = int(zone_id_str)
            mapped_zones[zone_id] = await self._build_zone(zone_id, raw_state)

        return mapped_zones

    async def _async_update_timetables(
        self, zone_ids: set[int]
    ) -> dict[int, Timetable]:
        """Update the timetable data from Tado."""
        try:
            return await self.hass.async_add_executor_job(
                self._load_timetables, list(zone_ids)
            )
        except RequestException as err:
            _LOGGER.warning("Error updating Tado timetables: %s", err)
            return self.data.get("timetable", {})

    def _load_timetables(self, zone_ids: list[int]) -> dict[int, Timetable]:
        """Load the active timetable for each zone."""
        timetables: dict[int, Timetable] = {}
        for zone_id in zone_ids:
            timetables[zone_id] = self._tado.get_timetable(zone_id)
        return timetables

    async def _build_zone(self, zone_id: int, raw_state: dict[str, Any]) -> TadoZone:
        """Fetch defaultOverlay for a zone and construct a TadoZone."""
        _LOGGER.debug("Updating zone %s", zone_id)
        try:
            overlay_default = await self.hass.async_add_executor_job(
                self._tado.get_zone_overlay_default, zone_id
            )
        except RequestException as err:
            _LOGGER.error("Error updating Tado zone %s: %s", zone_id, err)
            raise UpdateFailed(f"Error updating Tado zone {zone_id}: {err}") from err

        data = TadoZone.from_data(zone_id, {**raw_state, **overlay_default})
        _LOGGER.debug("Zone %s updated, with data: %s", zone_id, data)
        return data

    async def _update_zone(self, zone_id: int) -> TadoZone:
        """Fetch the latest state for a single zone (used after overlay changes)."""
        _LOGGER.debug("Refreshing zone %s after overlay change", zone_id)
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
        """Update the home data from Tado."""

        def _get_home_data() -> tuple[dict, dict]:
            """Get the weather and geofence data for the home."""
            return self._tado.get_weather(), self._tado.get_home_state()

        try:
            weather, geofence = await self.hass.async_add_executor_job(_get_home_data)
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
        """Fetch the capabilities from Tado."""

        try:
            return await self.hass.async_add_executor_job(
                self._tado.get_capabilities, zone_id
            )
        except RequestException as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def get_auto_geofencing_supported(self) -> bool:
        """Fetch the auto geofencing supported from Tado."""

        try:
            return await self.hass.async_add_executor_job(
                self._tado.get_auto_geofencing_supported
            )
        except RequestException as err:
            raise UpdateFailed(f"Error updating Tado data: {err}") from err

    async def reset_zone_overlay(self, zone_id):
        """Reset the zone back to the default operation."""

        try:
            await self.hass.async_add_executor_job(
                self._tado.reset_zone_overlay, zone_id
            )
            await self._update_zone(zone_id)
        except RequestException as err:
            raise UpdateFailed(f"Error resetting Tado data: {err}") from err

    async def set_presence(
        self,
        presence=PRESET_HOME,
    ):
        """Set the presence to home, away or auto."""

        if presence == PRESET_AWAY:
            await self.hass.async_add_executor_job(self._tado.set_away)
        elif presence == PRESET_HOME:
            await self.hass.async_add_executor_job(self._tado.set_home)
        elif presence == PRESET_AUTO:
            await self.hass.async_add_executor_job(self._tado.set_auto)

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
            "Set overlay for zone %s: overlay_mode=%s,"
            " temp=%s, duration=%s, type=%s, mode=%s,"
            " fan_speed=%s, swing=%s, fan_level=%s,"
            " vertical_swing=%s, horizontal_swing=%s",
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

        except RequestException as err:
            raise UpdateFailed(f"Error setting Tado overlay: {err}") from err

        await self._update_zone(zone_id)

    async def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
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
        except RequestException as err:
            raise UpdateFailed(f"Error setting Tado overlay: {err}") from err

        await self._update_zone(zone_id)

    async def set_temperature_offset(self, device_id, offset):
        """Set temperature offset of device."""
        try:
            await self.hass.async_add_executor_job(
                self._tado.set_temp_offset, device_id, offset
            )
        except RequestException as err:
            raise UpdateFailed(f"Error setting Tado temperature offset: {err}") from err

    async def set_meter_reading(self, reading: int) -> dict[str, Any]:
        """Send meter reading to Tado."""
        dt: str = datetime.now().strftime("%Y-%m-%d")  # pylint: disable=home-assistant-enforce-naive-now
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
        try:
            await self.hass.async_add_executor_job(
                self._tado.set_child_lock,
                device_id,
                enabled,
            )
        except RequestException as exc:
            raise HomeAssistantError(f"Error setting Tado child lock: {exc}") from exc

    def get_rate_limit(self) -> dict[str, str]:
        """Get the current rate limit status from Tado."""
        return self._tado.rate_limit_info()

    async def set_timetable(self, zone_id: int, timetable: Timetable) -> None:
        """Set timetable of a zone."""
        try:
            await self.hass.async_add_executor_job(
                self._tado.set_timetable,
                zone_id,
                timetable,
            )
        except RequestException as exc:
            raise HomeAssistantError(
                f"Error setting Tado timetable {timetable} for zone {zone_id}: {exc}"
            ) from exc
        self.data["timetable"][zone_id] = timetable
