"""Support for Mopar vehicles."""
from datetime import timedelta
import logging

import motorparts
import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

DOMAIN = "mopar"
DATA_UPDATED = f"{DOMAIN}_data_updated"

_LOGGER = logging.getLogger(__name__)

COOKIE_FILE = "mopar_cookies.pickle"
SUCCESS_RESPONSE = "completed"

SUPPORTED_PLATFORMS = [LOCK, SENSOR, SWITCH]

DEFAULT_INTERVAL = timedelta(days=7)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_PIN): cv.positive_int,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_HORN = "sound_horn"
ATTR_VEHICLE_INDEX = "vehicle_index"
SERVICE_HORN_SCHEMA = vol.Schema({vol.Required(ATTR_VEHICLE_INDEX): cv.positive_int})


def setup(hass, config):
    """Set up the Mopar component."""
    conf = config[DOMAIN]
    cookie = hass.config.path(COOKIE_FILE)
    try:
        session = motorparts.get_session(
            conf[CONF_USERNAME], conf[CONF_PASSWORD], conf[CONF_PIN], cookie_path=cookie
        )
    except motorparts.MoparError:
        _LOGGER.error("Failed to login")
        return False

    data = hass.data[DOMAIN] = MoparData(hass, session)
    data.update(now=None)

    track_time_interval(hass, data.update, conf[CONF_SCAN_INTERVAL])

    def handle_horn(call):
        """Enable the horn on the Mopar vehicle."""
        data.actuate("horn", call.data[ATTR_VEHICLE_INDEX])

    hass.services.register(
        DOMAIN, SERVICE_HORN, handle_horn, schema=SERVICE_HORN_SCHEMA
    )

    for platform in SUPPORTED_PLATFORMS:
        load_platform(hass, platform, DOMAIN, {}, config)

    return True


class MoparData:
    """
    Container for Mopar vehicle data.

    Prevents session expiry re-login race condition.
    """

    def __init__(self, hass, session):
        """Initialize data."""
        self._hass = hass
        self._session = session
        self.vehicles = []
        self.vhrs = {}
        self.tow_guides = {}

    def update(self, now, **kwargs):
        """Update data."""
        _LOGGER.debug("Updating vehicle data")
        try:
            self.vehicles = motorparts.get_summary(self._session)["vehicles"]
        except motorparts.MoparError:
            _LOGGER.exception("Failed to get summary")
            return

        for index, _ in enumerate(self.vehicles):
            try:
                self.vhrs[index] = motorparts.get_report(self._session, index)
                self.tow_guides[index] = motorparts.get_tow_guide(self._session, index)
            except motorparts.MoparError:
                _LOGGER.warning("Failed to update for vehicle index %s", index)
                return

        dispatcher_send(self._hass, DATA_UPDATED)

    @property
    def attribution(self):
        """Get the attribution string from Mopar."""
        return motorparts.ATTRIBUTION

    def get_vehicle_name(self, index):
        """Get the name corresponding with this vehicle."""
        vehicle = self.vehicles[index]
        if not vehicle:
            return None
        return f"{vehicle['year']} {vehicle['make']} {vehicle['model']}"

    def actuate(self, command, index):
        """Run a command on the specified Mopar vehicle."""
        try:
            response = getattr(motorparts, command)(self._session, index)
        except motorparts.MoparError as error:
            _LOGGER.error(error)
            return False

        return response == SUCCESS_RESPONSE
