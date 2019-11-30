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

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tado"

SIGNAL_TADO_UPDATE_RECEIVED = "tado_update_received_{}"

TADO_COMPONENTS = ["sensor", "climate", "water_heater"]

TYPE_AIR_CONDITIONING = "AIR_CONDITIONING"
TYPE_HEATING = "HEATING"
TYPE_HOT_WATER = "HOT_WATER"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
SCAN_INTERVAL = timedelta(seconds=15)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up of the Tado component."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    try:
        tado = Tado(username, password)
        tado.setDebugging(True)
    except (RuntimeError, urllib.error.HTTPError):
        _LOGGER.error("Unable to connect to Tado with username and password")
        return False

    hass.data[DOMAIN] = TadoConnector(tado, hass)

    for component in TADO_COMPONENTS:
        load_platform(hass, component, DOMAIN, {}, config)

    # Poll for updates in the background
    hass.helpers.event.track_time_interval(
        lambda now: hass.data[DOMAIN].update(), SCAN_INTERVAL
    )

    return True


class TadoConnector:
    """An object to store the Tado data."""

    def __init__(self, tado, hass):
        """Initialize Tado Connector."""
        self.tado = tado
        self.hass = hass
        self.sensors = []

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the internal data from Tado."""
        for sensor, sensor_type in self.sensors:
            _LOGGER.debug("Updating %s %s", sensor_type, sensor)
            try:
                if sensor_type == "zone":
                    data = self.tado.getState(sensor)
                elif sensor_type == "device":
                    data = self.tado.getDevices()[0]
                else:
                    continue

                dispatcher_send(
                    self.hass, SIGNAL_TADO_UPDATE_RECEIVED.format(sensor), data
                )
            except RuntimeError:
                _LOGGER.error(
                    "Unable to connect to Tado while updating %s %s",
                    sensor_type,
                    sensor,
                )

    def add_sensor(self, sensor, sensor_type):
        """Add a sensor to update."""
        if (sensor, sensor_type) not in self.sensors:
            _LOGGER.debug("Registering sensor %s %s", sensor_type, sensor)
            self.sensors.append((sensor, sensor_type))

    def get_zones(self):
        """Return the zones."""
        return self.tado.getZones()

    def get_capabilities(self, tado_id):
        """Return the capabilities of the devices."""
        return self.tado.getCapabilities(tado_id)

    def get_me(self):
        """Return information about the devices."""
        return self.tado.getMe()

    def reset_zone_overlay(self, zone_id):
        """Reset the zone back to the default operation."""
        self.tado.resetZoneOverlay(zone_id)
        self.update(no_throttle=True)  # pylint: disable=unexpected-keyword-arg

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
        self.tado.setZoneOverlay(
            zone_id, overlay_mode, temperature, duration, device_type, "ON", mode
        )
        self.update(no_throttle=True)  # pylint: disable=unexpected-keyword-arg

    def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        self.tado.setZoneOverlay(zone_id, overlay_mode, None, None, device_type, "OFF")
        self.update(no_throttle=True)  # pylint: disable=unexpected-keyword-arg
