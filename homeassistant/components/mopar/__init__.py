"""
Support for Mopar vehicles.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mopar/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_PIN
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util import Throttle

REQUIREMENTS = ['motorparts==1.1.0']

DOMAIN = 'mopar'
DATA_UPDATED = '{}_data_updated'.format(DOMAIN)

_LOGGER = logging.getLogger(__name__)

ATTR_VEHICLE_INDEX = 'vehicle_index'

COOKIE_FILE = 'mopar_cookies.pickle'

MIN_TIME_BETWEEN_UPDATES = timedelta(days=7)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_PIN): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Mopar component."""
    import motorparts
    cookie = hass.config.path(COOKIE_FILE)
    try:
        session = motorparts.get_session(
            config.get(CONF_USERNAME), config.get(CONF_PASSWORD),
            config.get(CONF_PIN), cookie_path=cookie)
    except motorparts.MoparError:
        _LOGGER.error("Failed to login")
        return False

    hass.data[DOMAIN] = MoparData(hass, session)
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
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Update data."""
        import motorparts
        _LOGGER.info("Updating vehicle data")
        try:
            self.vehicles = motorparts.get_summary(self._session)['vehicles']
        except motorparts.MoparError:
            _LOGGER.exception("Failed to get summary")
            return

        for index, _ in enumerate(self.vehicles):
            try:
                self.vhrs[index] = motorparts.get_report(self._session, index)
                self.tow_guides[index] = motorparts.get_tow_guide(
                    self._session, index)
            except motorparts.MoparError:
                _LOGGER.warning("Failed to update for vehicle index %s", index)
                return

        dispatcher_send(self._hass, DATA_UPDATED)

    @property
    def attribution(self):
        """Get the attribution string from Mopar."""
        import motorparts
        return motorparts.ATTRIBUTION
