"""Tado Connector a class to store the data as an object."""

from datetime import datetime, timedelta
import logging
from typing import Any

from PyTado.interface import Tado
from requests import RequestException

from homeassistant.components.climate import PRESET_AWAY, PRESET_HOME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util import Throttle

from .const import (
    INSIDE_TEMPERATURE_MEASUREMENT,
    PRESET_AUTO,
    SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TEMP_OFFSET,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(minutes=5)
SCAN_MOBILE_DEVICE_INTERVAL = timedelta(seconds=30)


_LOGGER = logging.getLogger(__name__)


class TadoConnector:
    """An object to store the Tado data."""

    def __init__(
        self, hass: HomeAssistant, username: str, password: str, fallback: str
    ) -> None:
        """Initialize Tado Connector."""
        self.hass = hass
        self._username = username
        self._password = password
        self._fallback = fallback

        self.home_id: int = 0
        self.home_name = None
        self.tado = None
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

    def setup(self):
        """Connect to Tado and fetch the zones."""
        self.tado = Tado(self._username, self._password)
        # Load zones and devices
        self.zones = self.tado.get_zones()
        self.devices = self.tado.get_devices()
        tado_home = self.tado.get_me()["homes"][0]
        self.home_id = tado_home["id"]
        self.home_name = tado_home["name"]

    def get_mobile_devices(self):
        """Return the Tado mobile devices."""
        return self.tado.get_mobile_devices()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the registered zones."""
        self.update_devices()
        self.update_mobile_devices()
        self.update_zones()
        self.update_home()

    def update_mobile_devices(self) -> None:
        """Update the mobile devices."""
        try:
            mobile_devices = self.get_mobile_devices()
        except RuntimeError:
            _LOGGER.error("Unable to connect to Tado while updating mobile devices")
            return

        if not mobile_devices:
            _LOGGER.debug("No linked mobile devices found for home ID %s", self.home_id)
            return

        # Errors are planned to be converted to exceptions
        # in PyTado library, so this can be removed
        if isinstance(mobile_devices, dict) and mobile_devices.get("errors"):
            _LOGGER.error(
                "Error for home ID %s while updating mobile devices: %s",
                self.home_id,
                mobile_devices["errors"],
            )
            return

        for mobile_device in mobile_devices:
            self.data["mobile_device"][mobile_device["id"]] = mobile_device
            _LOGGER.debug(
                "Dispatching update to %s mobile device: %s",
                self.home_id,
                mobile_device,
            )

        dispatcher_send(
            self.hass,
            SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED.format(self.home_id),
        )

    def update_devices(self):
        """Update the device data from Tado."""
        try:
            devices = self.tado.get_devices()
        except RuntimeError:
            _LOGGER.error("Unable to connect to Tado while updating devices")
            return

        if not devices:
            _LOGGER.debug("No linked devices found for home ID %s", self.home_id)
            return

        # Errors are planned to be converted to exceptions
        # in PyTado library, so this can be removed
        if isinstance(devices, dict) and devices.get("errors"):
            _LOGGER.error(
                "Error for home ID %s while updating devices: %s",
                self.home_id,
                devices["errors"],
            )
            return

        for device in devices:
            device_short_serial_no = device["shortSerialNo"]
            _LOGGER.debug("Updating device %s", device_short_serial_no)
            try:
                if (
                    INSIDE_TEMPERATURE_MEASUREMENT
                    in device["characteristics"]["capabilities"]
                ):
                    device[TEMP_OFFSET] = self.tado.get_device_info(
                        device_short_serial_no, TEMP_OFFSET
                    )
            except RuntimeError:
                _LOGGER.error(
                    "Unable to connect to Tado while updating device %s",
                    device_short_serial_no,
                )
                return

            self.data["device"][device_short_serial_no] = device

            _LOGGER.debug(
                "Dispatching update to %s device %s: %s",
                self.home_id,
                device_short_serial_no,
                device,
            )
            dispatcher_send(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self.home_id, "device", device_short_serial_no
                ),
            )

    def update_zones(self):
        """Update the zone data from Tado."""
        try:
            zone_states = self.tado.get_zone_states()["zoneStates"]
        except RuntimeError:
            _LOGGER.error("Unable to connect to Tado while updating zones")
            return

        for zone in zone_states:
            self.update_zone(int(zone))

    def update_zone(self, zone_id):
        """Update the internal data from Tado."""
        _LOGGER.debug("Updating zone %s", zone_id)
        try:
            data = self.tado.get_zone_state(zone_id)
        except RuntimeError:
            _LOGGER.error("Unable to connect to Tado while updating zone %s", zone_id)
            return

        self.data["zone"][zone_id] = data

        _LOGGER.debug(
            "Dispatching update to %s zone %s: %s",
            self.home_id,
            zone_id,
            data,
        )
        dispatcher_send(
            self.hass,
            SIGNAL_TADO_UPDATE_RECEIVED.format(self.home_id, "zone", zone_id),
        )

    def update_home(self):
        """Update the home data from Tado."""
        try:
            self.data["weather"] = self.tado.get_weather()
            self.data["geofence"] = self.tado.get_home_state()
            dispatcher_send(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(self.home_id, "home", "data"),
            )
        except RuntimeError:
            _LOGGER.error(
                "Unable to connect to Tado while updating weather and geofence data"
            )
            return

    def get_capabilities(self, zone_id):
        """Return the capabilities of the devices."""
        return self.tado.get_capabilities(zone_id)

    def get_auto_geofencing_supported(self):
        """Return whether the Tado Home supports auto geofencing."""
        return self.tado.get_auto_geofencing_supported()

    def reset_zone_overlay(self, zone_id):
        """Reset the zone back to the default operation."""
        self.tado.reset_zone_overlay(zone_id)
        self.update_zone(zone_id)

    def set_presence(
        self,
        presence=PRESET_HOME,
    ):
        """Set the presence to home, away or auto."""
        if presence == PRESET_AWAY:
            self.tado.set_away()
        elif presence == PRESET_HOME:
            self.tado.set_home()
        elif presence == PRESET_AUTO:
            self.tado.set_auto()

        # Update everything when changing modes
        self.update_zones()
        self.update_home()

    def set_zone_overlay(
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
    ):
        """Set a zone overlay."""
        _LOGGER.debug(
            (
                "Set overlay for zone %s: overlay_mode=%s, temp=%s, duration=%s,"
                " type=%s, mode=%s fan_speed=%s swing=%s fan_level=%s vertical_swing=%s horizontal_swing=%s"
            ),
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
            self.tado.set_zone_overlay(
                zone_id,
                overlay_mode,
                temperature,
                duration,
                device_type,
                "ON",
                mode,
                fan_speed=fan_speed,
                swing=swing,
                fan_level=fan_level,
                vertical_swing=vertical_swing,
                horizontal_swing=horizontal_swing,
            )

        except RequestException as exc:
            _LOGGER.error("Could not set zone overlay: %s", exc)

        self.update_zone(zone_id)

    def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        try:
            self.tado.set_zone_overlay(
                zone_id, overlay_mode, None, None, device_type, "OFF"
            )
        except RequestException as exc:
            _LOGGER.error("Could not set zone overlay: %s", exc)

        self.update_zone(zone_id)

    def set_temperature_offset(self, device_id, offset):
        """Set temperature offset of device."""
        try:
            self.tado.set_temp_offset(device_id, offset)
        except RequestException as exc:
            _LOGGER.error("Could not set temperature offset: %s", exc)

    def set_meter_reading(self, reading: int) -> dict[str, Any]:
        """Send meter reading to Tado."""
        dt: str = datetime.now().strftime("%Y-%m-%d")
        if self.tado is None:
            raise HomeAssistantError("Tado client is not initialized")

        try:
            return self.tado.set_eiq_meter_readings(date=dt, reading=reading)
        except RequestException as exc:
            raise HomeAssistantError("Could not set meter reading") from exc
