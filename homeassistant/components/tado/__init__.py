"""Support for the (unofficial) Tado API."""
from datetime import timedelta
import logging
import urllib

from PyTado.interface import Tado
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util import Throttle

from .const import CONF_FALLBACK, DATA

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tado"

SIGNAL_TADO_UPDATE_RECEIVED = "tado_update_received_{}_{}"

TADO_COMPONENTS = ["sensor", "climate", "water_heater"]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
SCAN_INTERVAL = timedelta(seconds=15)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_FALLBACK, default=True): cv.boolean,
                }
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up of the Tado component."""
    acc_list = config[DOMAIN]

    api_data_list = []

    for acc in acc_list:
        username = acc[CONF_USERNAME]
        password = acc[CONF_PASSWORD]
        fallback = acc[CONF_FALLBACK]

        tadoconnector = TadoConnector(hass, username, password, fallback)
        if not tadoconnector.setup():
            continue

        # Do first update
        tadoconnector.update()

        api_data_list.append(tadoconnector)
        # Poll for updates in the background
        hass.helpers.event.track_time_interval(
            # we're using here tadoconnector as a parameter of lambda
            # to capture actual value instead of closuring of latest value
            lambda now, tc=tadoconnector: tc.update(),
            SCAN_INTERVAL,
        )

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA] = api_data_list

    # Load components
    for component in TADO_COMPONENTS:
        load_platform(
            hass, component, DOMAIN, {}, config,
        )

    return True


class TadoConnector:
    """An object to store the Tado data."""

    def __init__(self, hass, username, password, fallback):
        """Initialize Tado Connector."""
        self.hass = hass
        self._username = username
        self._password = password
        self._fallback = fallback

        self.device_id = None
        self.tado = None
        self.zones = None
        self.devices = None
        self.data = {
            "zone": {},
            "device": {},
        }

    @property
    def fallback(self):
        """Return fallback flag to Smart Schedule."""
        return self._fallback

    def setup(self):
        """Connect to Tado and fetch the zones."""
        try:
            self.tado = Tado(self._username, self._password)
        except (RuntimeError, urllib.error.HTTPError) as exc:
            _LOGGER.error("Unable to connect: %s", exc)
            return False

        self.tado.setDebugging(True)

        # Load zones and devices
        self.zones = self.tado.getZones()
        self.devices = self.tado.getMe()["homes"]
        self.device_id = self.devices[0]["id"]
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the registered zones."""
        for zone in self.zones:
            self.update_sensor("zone", zone["id"])
        for device in self.devices:
            self.update_sensor("device", device["id"])

    def update_sensor(self, sensor_type, sensor):
        """Update the internal data from Tado."""
        _LOGGER.debug("Updating %s %s", sensor_type, sensor)
        try:
            if sensor_type == "zone":
                data = self.tado.getState(sensor)
            elif sensor_type == "device":
                data = self.tado.getDevices()[0]
            else:
                _LOGGER.debug("Unknown sensor: %s", sensor_type)
                return
        except RuntimeError:
            _LOGGER.error(
                "Unable to connect to Tado while updating %s %s", sensor_type, sensor,
            )
            return

        self.data[sensor_type][sensor] = data

        _LOGGER.debug("Dispatching update to %s %s: %s", sensor_type, sensor, data)
        dispatcher_send(
            self.hass, SIGNAL_TADO_UPDATE_RECEIVED.format(sensor_type, sensor)
        )

    def get_capabilities(self, zone_id):
        """Return the capabilities of the devices."""
        return self.tado.getCapabilities(zone_id)

    def reset_zone_overlay(self, zone_id):
        """Reset the zone back to the default operation."""
        self.tado.resetZoneOverlay(zone_id)
        self.update_sensor("zone", zone_id)

    def set_zone_overlay(
        self,
        zone_id,
        overlay_mode,
        temperature=None,
        duration=None,
        device_type="HEATING",
        mode=None,
    ):
        """Set a zone overlay."""
        _LOGGER.debug(
            "Set overlay for zone %s: mode=%s, temp=%s, duration=%s, type=%s, mode=%s",
            zone_id,
            overlay_mode,
            temperature,
            duration,
            device_type,
            mode,
        )
        try:
            self.tado.setZoneOverlay(
                zone_id, overlay_mode, temperature, duration, device_type, "ON", mode
            )
        except urllib.error.HTTPError as exc:
            _LOGGER.error("Could not set zone overlay: %s", exc.read())

        self.update_sensor("zone", zone_id)

    def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        try:
            self.tado.setZoneOverlay(
                zone_id, overlay_mode, None, None, device_type, "OFF"
            )
        except urllib.error.HTTPError as exc:
            _LOGGER.error("Could not set zone overlay: %s", exc.read())

        self.update_sensor("zone", zone_id)
