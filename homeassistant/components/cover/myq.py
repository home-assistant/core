"""
Support for MyQ-Enabled Garage Doors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.myq/
"""
import logging
from datetime import timedelta
from time import sleep
import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice, SUPPORT_CLOSE, SUPPORT_OPEN)
from homeassistant.const import (
    CONF_PASSWORD, CONF_TYPE, CONF_USERNAME, STATE_CLOSED, STATE_CLOSING,
    STATE_OPEN, STATE_OPENING)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pymyq==0.0.16']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'myq'

MYQ_TO_HASS = {
    'closed': STATE_CLOSED,
    'closing': STATE_CLOSING,
    'open': STATE_OPEN,
    'opening': STATE_OPENING
}

NOTIFICATION_ID = 'myq_notification'
NOTIFICATION_TITLE = 'MyQ Cover Setup'

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_TYPE): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

SCAN_INTERVAL = timedelta(seconds=120)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MyQ component."""
    from pymyq import MyQAPI as pymyq

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    brand = config.get(CONF_TYPE)
    myq = pymyq(username, password, brand)

    try:
        if not myq.is_supported_brand():
            raise ValueError("Unsupported type. See documentation")

        if not myq.is_login_valid():
            raise ValueError("Username or Password is incorrect")

        add_entities(MyQDevice(myq, door) for door in myq.get_garage_doors())
        return True

    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False


class MyQDevice(CoverDevice):
    """Representation of a MyQ cover."""

    def __init__(self, myq, device):
        """Initialize with API object, device id."""
        self.myq = myq
        self.device_id = device['deviceid']
        self._name = device['name']

        if self.myq.get_status(self.device_id):
            self._status = self.myq.get_status(self.device_id)
        else:
            self._status = None

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        return 'garage'

    @property
    def should_poll(self):
        """Poll for state."""
        return True

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._name if self._name else DEFAULT_NAME

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        if self._status in [None, False]:
            return None
        return MYQ_TO_HASS.get(self._status) == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return MYQ_TO_HASS.get(self._status) == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return MYQ_TO_HASS.get(self._status) == STATE_OPENING

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        iterations = 0
        while True:
            if self.myq.close_device(self.device_id):
                break
            if iterations > 5:
                _LOGGER.error(
                    "Failed to close %s "
                    "after 6 attempts", self._name)
                break
            iterations += 1
            sleep(10)

        if iterations <= 5:
            closed_confired_interations = 0
            while True:
                self._status = self.myq.get_status(self.device_id)
                if self._status == STATE_CLOSED:
                    break
                if closed_confired_interations > 5:
                    _LOGGER.error(
                        "Failed to confirm closed status for %s "
                        "after 60 seconds", self._name)
                    self._status = None
                    break
                closed_confired_interations += 1
                sleep(10)

        return iterations <= 5 and closed_confired_interations <= 5

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        iterations = 0
        while True:
            if self.myq.open_device(self.device_id):
                break
            if iterations > 5:
                _LOGGER.error(
                    "Failed to open %s "
                    "after 6 attempts", self._name)
                break
            iterations += 1
            sleep(10)

        if iterations <= 5:
            open_confirmed_interations = 0
            while True:
                self._status = self.myq.get_status(self.device_id)
                if self._status == STATE_OPEN:
                    break
                if open_confirmed_interations > 5:
                    _LOGGER.error(
                        "Failed to confirm open status for %s "
                        "after 60 seconds", self._name)
                    self._status = None
                    break
                open_confirmed_interations += 1
                sleep(10)

        return iterations <= 5 and open_confirmed_interations <= 5

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self.device_id

    def update(self):
        """Update status of cover."""
        current = self.myq.get_status(self.device_id)
        if current is not False:
            self._status = current
        else:
            self._status = None
