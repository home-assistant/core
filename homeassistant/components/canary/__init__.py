"""Support for Canary devices."""
from datetime import timedelta
import logging

from canary.api import Api
from requests import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "canary_notification"
NOTIFICATION_TITLE = "Canary Setup"

DOMAIN = "canary"
DATA_CANARY = "canary"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
DEFAULT_TIMEOUT = 10

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CANARY_COMPONENTS = ["alarm_control_panel", "camera", "sensor"]


def setup(hass, config):
    """Set up the Canary component."""
    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    timeout = conf[CONF_TIMEOUT]

    try:
        hass.data[DATA_CANARY] = CanaryData(username, password, timeout)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Canary service: %s", str(ex))
        hass.components.persistent_notification.create(
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    for component in CANARY_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class CanaryData:
    """Get the latest data and update the states."""

    def __init__(self, username, password, timeout):
        """Init the Canary data object."""

        self._api = Api(username, password, timeout)

        self._locations_by_id = {}
        self._readings_by_device_id = {}
        self._entries_by_location_id = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Get the latest data from py-canary."""
        for location in self._api.get_locations():
            location_id = location.location_id

            self._locations_by_id[location_id] = location
            self._entries_by_location_id[location_id] = self._api.get_entries(
                location_id, entry_type="motion", limit=1
            )

            for device in location.devices:
                if device.is_online:
                    self._readings_by_device_id[
                        device.device_id
                    ] = self._api.get_latest_readings(device.device_id)

    @property
    def locations(self):
        """Return a list of locations."""
        return self._locations_by_id.values()

    def get_motion_entries(self, location_id):
        """Return a list of motion entries based on location_id."""
        return self._entries_by_location_id.get(location_id, [])

    def get_location(self, location_id):
        """Return a location based on location_id."""
        return self._locations_by_id.get(location_id, [])

    def get_readings(self, device_id):
        """Return a list of readings based on device_id."""
        return self._readings_by_device_id.get(device_id, [])

    def get_reading(self, device_id, sensor_type):
        """Return reading for device_id and sensor type."""
        readings = self._readings_by_device_id.get(device_id, [])
        return next(
            (
                reading.value
                for reading in readings
                if reading.sensor_type == sensor_type
            ),
            None,
        )

    def set_location_mode(self, location_id, mode_name, is_private=False):
        """Set location mode."""
        self._api.set_location_mode(location_id, mode_name, is_private)
        self.update(no_throttle=True)

    def get_live_stream_session(self, device):
        """Return live stream session."""
        return self._api.get_live_stream_session(device)
