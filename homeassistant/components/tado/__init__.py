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

from .const import CONF_FALLBACK

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tado"

SIGNAL_TADO_UPDATE_RECEIVED = "tado_update_received_{}_{}"

TADO_COMPONENTS = ["sensor", "climate"]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
SCAN_INTERVAL = timedelta(seconds=15)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_FALLBACK, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up of the Tado component."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    tadoconnector = TadoConnector(hass, username, password)
    hass.data[DOMAIN] = tadoconnector

    # Do first update
    tadoconnector.update()

    # Load components
    for component in TADO_COMPONENTS:
        load_platform(
            hass,
            component,
            DOMAIN,
            {CONF_FALLBACK: config[DOMAIN][CONF_FALLBACK]},
            config,
        )

    # Poll for updates in the background
    hass.helpers.event.track_time_interval(
        lambda now: tadoconnector.update(), SCAN_INTERVAL
    )

    return True


class TadoConnector:
    """An object to store the Tado data."""

    def __init__(self, hass, username, password):
        """Initialize Tado Connector."""
        self.hass = hass

        try:
            self.tado = Tado(username, password)
            self.tado.setDebugging(True)
        except (RuntimeError, urllib.error.HTTPError) as e:
            _LOGGER.error("Unable to connect to Tado with username and password")
            raise e

        # Load zones and devices
        self.zones = self.tado.getZones()
        self.devices = self.tado.getMe()["homes"]

        self.sensors = []
        for zone in self.zones:
            _LOGGER.debug("Registering zone %s (%s)", zone["name"], zone["id"])
            self.sensors.append(("zone", zone["id"]))

        for device in self.devices:
            _LOGGER.debug("Registering device %s (%s)", device["name"], device["id"])
            self.sensors.append(("device", device["id"]))

        self.data = {
            "zone": {},
            "device": {},
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the registered zones."""
        for sensor_type, sensor in self.sensors:
            self.update_sensor(sensor_type, sensor)

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

            self.data[sensor_type][sensor] = data
            _LOGGER.debug("Dispatching update to %s %s: %s", sensor_type, sensor, data)
            dispatcher_send(
                self.hass, SIGNAL_TADO_UPDATE_RECEIVED.format(sensor_type, sensor)
            )
        except RuntimeError:
            _LOGGER.error(
                "Unable to connect to Tado while updating %s %s", sensor_type, sensor,
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
        self.tado.setZoneOverlay(
            zone_id, overlay_mode, temperature, duration, device_type, "ON", mode
        )
        self.update_sensor("zone", zone_id)

    def set_zone_off(self, zone_id, overlay_mode, device_type="HEATING"):
        """Set a zone to off."""
        self.tado.setZoneOverlay(zone_id, overlay_mode, None, None, device_type, "OFF")
        self.update_sensor("zone", zone_id)
