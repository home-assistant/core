"""Support for the (unofficial) Tado API."""
from datetime import timedelta
import logging

from PyTado.interface import Tado
from PyTado.zone import TadoZone
from requests import RequestException
import requests.exceptions

from homeassistant.components.climate.const import PRESET_AWAY, PRESET_HOME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import Throttle

from .const import (
    CONF_FALLBACK,
    DATA,
    DOMAIN,
    INSIDE_TEMPERATURE_MEASUREMENT,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TEMP_OFFSET,
    UPDATE_LISTENER,
    UPDATE_TRACK,
)

_LOGGER = logging.getLogger(__name__)


PLATFORMS = ["binary_sensor", "sensor", "climate", "water_heater"]

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(minutes=5)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tado from a config entry."""

    _async_import_options_from_data_if_missing(hass, entry)

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    fallback = entry.options.get(CONF_FALLBACK, True)

    tadoconnector = TadoConnector(hass, username, password, fallback)

    try:
        await hass.async_add_executor_job(tadoconnector.setup)
    except KeyError:
        _LOGGER.error("Failed to login to tado")
        return False
    except RuntimeError as exc:
        _LOGGER.error("Failed to setup tado: %s", exc)
        return False
    except requests.exceptions.Timeout as ex:
        raise ConfigEntryNotReady from ex
    except requests.exceptions.HTTPError as ex:
        if ex.response.status_code > 400 and ex.response.status_code < 500:
            _LOGGER.error("Failed to login to tado: %s", ex)
            return False
        raise ConfigEntryNotReady from ex

    # Do first update
    await hass.async_add_executor_job(tadoconnector.update)

    # Poll for updates in the background
    update_track = async_track_time_interval(
        hass,
        lambda now: tadoconnector.update(),
        SCAN_INTERVAL,
    )

    update_listener = entry.add_update_listener(_async_update_listener)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA: tadoconnector,
        UPDATE_TRACK: update_track,
        UPDATE_LISTENER: update_listener,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    if CONF_FALLBACK not in options:
        options[CONF_FALLBACK] = entry.data.get(CONF_FALLBACK, True)
        hass.config_entries.async_update_entry(entry, options=options)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][UPDATE_TRACK]()
    hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class TadoConnector:
    """An object to store the Tado data."""

    def __init__(self, hass, username, password, fallback):
        """Initialize Tado Connector."""
        self.hass = hass
        self._username = username
        self._password = password
        self._fallback = fallback

        self.home_id = None
        self.home_name = None
        self.tado = None
        self.zones = None
        self.devices = None
        self.data = {
            "device": {},
            "weather": {},
            "zone": {},
        }

    @property
    def fallback(self):
        """Return fallback flag to Smart Schedule."""
        return self._fallback

    def setup(self):
        """Connect to Tado and fetch the zones."""
        self.tado = Tado(self._username, self._password)
        self.tado.setDebugging(True)
        # Load zones and devices
        self.zones = self.tado.getZones()
        self.devices = self.tado.getDevices()
        tado_home = self.tado.getMe()["homes"][0]
        self.home_id = tado_home["id"]
        self.home_name = tado_home["name"]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the registered zones."""
        self.update_devices()
        self.update_zones()
        self.data["weather"] = self.tado.getWeather()
        dispatcher_send(
            self.hass,
            SIGNAL_TADO_UPDATE_RECEIVED.format(self.home_id, "weather", "data"),
        )

    def update_devices(self):
        """Update the device data from Tado."""
        devices = self.tado.getDevices()
        for device in devices:
            device_short_serial_no = device["shortSerialNo"]
            _LOGGER.debug("Updating device %s", device_short_serial_no)
            try:
                if (
                    INSIDE_TEMPERATURE_MEASUREMENT
                    in device["characteristics"]["capabilities"]
                ):
                    device[TEMP_OFFSET] = self.tado.getDeviceInfo(
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
            zone_states = self.tado.getZoneStates()["zoneStates"]
        except RuntimeError:
            _LOGGER.error("Unable to connect to Tado while updating zones")
            return

        for zone in self.zones:
            zone_id = zone["id"]
            _LOGGER.debug("Updating zone %s", zone_id)
            zone_state = TadoZone(zone_states[str(zone_id)], zone_id)

            self.data["zone"][zone_id] = zone_state

            _LOGGER.debug(
                "Dispatching update to %s zone %s: %s",
                self.home_id,
                zone_id,
                zone_state,
            )
            dispatcher_send(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(self.home_id, "zone", zone["id"]),
            )

    def update_zone(self, zone_id):
        """Update the internal data from Tado."""
        _LOGGER.debug("Updating zone %s", zone_id)
        try:
            data = self.tado.getZoneState(zone_id)
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

    def get_capabilities(self, zone_id):
        """Return the capabilities of the devices."""
        return self.tado.getCapabilities(zone_id)

    def reset_zone_overlay(self, zone_id):
        """Reset the zone back to the default operation."""
        self.tado.resetZoneOverlay(zone_id)
        self.update_zone(zone_id)

    def set_presence(
        self,
        presence=PRESET_HOME,
    ):
        """Set the presence to home or away."""
        if presence == PRESET_AWAY:
            self.tado.setAway()
        elif presence == PRESET_HOME:
            self.tado.setHome()

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
    ):
        """Set a zone overlay."""
        _LOGGER.debug(
            "Set overlay for zone %s: overlay_mode=%s, temp=%s, duration=%s, type=%s, mode=%s fan_speed=%s swing=%s",
            zone_id,
            overlay_mode,
            temperature,
            duration,
            device_type,
            mode,
            fan_speed,
            swing,
        )

        try:
            self.tado.setZoneOverlay(
                zone_id,
                overlay_mode,
                temperature,
                duration,
                device_type,
                "ON",
                mode,
                fanSpeed=fan_speed,
                swing=swing,
            )

        except RequestException as exc:
            _LOGGER.error("Could not set zone overlay: %s", exc)

        self.update_zone(zone_id)

    def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        try:
            self.tado.setZoneOverlay(
                zone_id, overlay_mode, None, None, device_type, "OFF"
            )
        except RequestException as exc:
            _LOGGER.error("Could not set zone overlay: %s", exc)

        self.update_zone(zone_id)

    def set_temperature_offset(self, device_id, offset):
        """Set temperature offset of device."""
        try:
            self.tado.setTempOffset(device_id, offset)
        except RequestException as exc:
            _LOGGER.error("Could not set temperature offset: %s", exc)
