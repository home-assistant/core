"""
Support for Brunt Blind Engine covers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cover/brunt
"""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_SET_POSITION,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    ATTR_POSITION, PLATFORM_SCHEMA,
=======
    ATTR_POSITION, PLATFORM_SCHEMA, SERVICE_OPEN_COVER, 
    SERVICE_CLOSE_COVER, SERVICE_SET_COVER_POSITION,
>>>>>>> 203699105... Added Brunt Cover device
=======
    ATTR_POSITION, PLATFORM_SCHEMA,
>>>>>>> 64ddfcc80... small styling updates
    STATE_OPEN, STATE_CLOSED)
=======
    ATTR_POSITION, PLATFORM_SCHEMA, ATTR_CURRENT_POSITION,
    STATE_OPEN, STATE_CLOSED, STATE_OPENING, STATE_CLOSING,
    STATE_UNKNOWN)
>>>>>>> d1da64c6f... Updated functional code, new state function and other small changes.
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['brunt==0.1.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'brunt'
ATTRIBUTION = 'Based on an unofficial Brunt SDK.'

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

# ATTR_COVER_STATE = 'cover_state'
STATE_PARTIALLY_OPEN = 'partially open'
ATTR_REQUEST_POSITION = 'request_position'
DEFAULT_NAME = 'brunt blind engine'
NOTIFICATION_ID = 'brunt_notification'
NOTIFICATION_TITLE = 'Brunt Cover Setup'

CLOSED_POSITION = 0
OPEN_POSITION = 100

<<<<<<< HEAD
<<<<<<< HEAD
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
<<<<<<< HEAD
})

POSITION_MAP = {
    0: STATE_CLOSED,
    100: STATE_OPEN,
}
MOVE_STATES_MAP = {
    1: STATE_OPENING,
    2: STATE_CLOSING,
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the brunt platform."""
    # pylint: disable=no-name-in-module
=======
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({     
=======
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
>>>>>>> 64ddfcc80... small styling updates
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
=======
>>>>>>> 166484267... fixed some linting errors.
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the brunt platform."""
<<<<<<< HEAD
>>>>>>> 203699105... Added Brunt Cover device
=======
    # pylint: disable=no-name-in-module
>>>>>>> 166484267... fixed some linting errors.
    from brunt import BruntAPI
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    bapi = BruntAPI(username=username, password=password)
    try:
        things = bapi.getThings()['things']
<<<<<<< HEAD
<<<<<<< HEAD
        if not things:
            raise HomeAssistantError

        add_devices(BruntDevice(
            hass, bapi, thing['NAME'],
            thing['thingUri']) for thing in things)
=======
        if len(things) == 0:
            raise HomeAssistantError

        add_devices(BruntDevice(
                hass, bapi, thing['NAME'],
                thing['thingUri']) for thing in things)
>>>>>>> 203699105... Added Brunt Cover device
=======
        if not things:
<<<<<<< HEAD
            raise HomeAssistantError

        add_devices(BruntDevice(
            hass, bapi, thing['NAME'],
            thing['thingUri']) for thing in things)
>>>>>>> 166484267... fixed some linting errors.
=======
            _LOGGER.error("No things present in account.")
        else:
            add_devices(BruntDevice(
                hass, bapi, thing['NAME'],
                thing['thingUri']) for thing in things)
>>>>>>> d1da64c6f... Updated functional code, new state function and other small changes.
    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)


class BruntDevice(CoverDevice):
    """Representation of a Brunt cover device.

    Contains the common logic for all Brunt devices.
    """

<<<<<<< HEAD
<<<<<<< HEAD
    def __init__(self, hass, bapi, name, thing_uri):
        """Init the Brunt device."""
        self._bapi = bapi
        self._name = name
        self._thing_uri = thing_uri
=======
    def __init__(self, hass, bapi, name, thingUri):
=======
    def __init__(self, hass, bapi, name, thing_uri):
>>>>>>> 166484267... fixed some linting errors.
        """Init the Brunt device."""
        self._bapi = bapi
        self._name = name
<<<<<<< HEAD
        self._thingUri = thingUri
>>>>>>> 203699105... Added Brunt Cover device
=======
        self._thing_uri = thing_uri
>>>>>>> 166484267... fixed some linting errors.

        self._state = STATE_UNKNOWN
        self._available = None
        self.update()

    @property
    def name(self):
        """Return the name of the device as reported by tellcore."""
        return self._name

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    @property
    def device_state_attributes(self):
<<<<<<< HEAD
        """Return the device state attributes."""
        data = {}
<<<<<<< HEAD
<<<<<<< HEAD
=======

>>>>>>> 203699105... Added Brunt Cover device
=======
>>>>>>> 64ddfcc80... small styling updates
        if self._state['moveState'] == 1:
            data[ATTR_COVER_STATE] = 'OPENING'
        elif self._state['moveState'] == 2:
            data[ATTR_COVER_STATE] = 'CLOSING'
        elif int(self._state['currentPosition']) == CLOSED_POSITION:
            data[ATTR_COVER_STATE] = 'CLOSED'
        elif int(self._state['currentPosition']) == OPEN_POSITION:
            data[ATTR_COVER_STATE] = 'OPENED'
<<<<<<< HEAD
<<<<<<< HEAD
        else:
            data[ATTR_COVER_STATE] = 'PARTIALLY OPENED'
        data[ATTR_CURRENT_POSITION] = int(self._state['currentPosition'])
        data[ATTR_REQUEST_POSITION] = int(self._state['requestPosition'])
=======
        else:            
=======
        else:
>>>>>>> 64ddfcc80... small styling updates
            data[ATTR_COVER_STATE] = 'PARTIALLY OPENED'
        data[ATTR_CURRENT_POSITION] = int(self._state['currentPosition'])
        data[ATTR_REQUEST_POSITION] = int(self._state['requestPosition'])
<<<<<<< HEAD

>>>>>>> 203699105... Added Brunt Cover device
=======
>>>>>>> 64ddfcc80... small styling updates
        return data
=======
        """Return the detailed device state attributes."""
        return {
            ATTR_CURRENT_POSITION: int(self._state['currentPosition']),
            ATTR_REQUEST_POSITION: int(self._state['requestPosition'])
        }
>>>>>>> d1da64c6f... Updated functional code, new state function and other small changes.

    @property
    def state(self):
        """Return the state of the cover. """
        if int(self._state['moveState']) in MOVE_STATES_MAP:
            state = MOVE_STATES_MAP.get(int(self._state['moveState']))
        elif 0 <= int(self._state['currentPosition']) <= 100:
            state = POSITION_MAP.get(int(self._state['currentPosition']), STATE_PARTIALLY_OPEN)
        else:
            state = STATE_UNKNOWN
        return state

    @property
    def current_cover_position(self):
        """
        Return current position of cover.
        None is unknown, 0 is closed, 100 is fully open.
        """
        return int(self._state['currentPosition'])

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'window'
<<<<<<< HEAD
<<<<<<< HEAD

=======
    
>>>>>>> 203699105... Added Brunt Cover device
=======

>>>>>>> 64ddfcc80... small styling updates
    @property
    def supported_features(self):
        """Flag supported features."""
        return COVER_FEATURES

    @property
    def is_closed(self):
        """"Return true if cover is closed, else False."""
        return int(self._state['currentPosition']) == CLOSED_POSITION

<<<<<<< HEAD
<<<<<<< HEAD
=======

>>>>>>> 203699105... Added Brunt Cover device
=======
>>>>>>> 64ddfcc80... small styling updates
    def update(self):
        """Poll the current state of the device."""
        try:
            self._state = self._bapi.getState(
<<<<<<< HEAD
<<<<<<< HEAD
                thingUri=self._thing_uri)['thing']
=======
                thingUri=self._thingUri)['thing']
>>>>>>> 203699105... Added Brunt Cover device
=======
                thingUri=self._thing_uri)['thing']
>>>>>>> 166484267... fixed some linting errors.
            self._available = True
        except (TypeError, KeyError, NameError, ValueError) as ex:
            _LOGGER.error("%s", ex)
            self._available = False

    def open_cover(self, **kwargs):
        """ set the cover to the open position. """
        self._bapi.changeRequestPosition(
<<<<<<< HEAD
<<<<<<< HEAD
            OPEN_POSITION, thingUri=self._thing_uri)
=======
            OPEN_POSITION, thingUri=self._thingUri)
=======
            OPEN_POSITION, thingUri=self._thing_uri)
>>>>>>> 166484267... fixed some linting errors.

<<<<<<< HEAD
>>>>>>> 203699105... Added Brunt Cover device

=======
>>>>>>> 64ddfcc80... small styling updates
    def close_cover(self, **kwargs):
        """ set the cover to the closed position. """
        self._bapi.changeRequestPosition(
<<<<<<< HEAD
<<<<<<< HEAD
            CLOSED_POSITION, thingUri=self._thing_uri)
=======
            CLOSED_POSITION, thingUri=self._thingUri)
>>>>>>> 203699105... Added Brunt Cover device
=======
            CLOSED_POSITION, thingUri=self._thing_uri)
>>>>>>> 166484267... fixed some linting errors.

    def set_cover_position(self, **kwargs):
        """ set the cover to a specific position. """
        if ATTR_POSITION in kwargs:
            self._bapi.changeRequestPosition(
<<<<<<< HEAD
<<<<<<< HEAD
                int(kwargs[ATTR_POSITION]), thingUri=self._thing_uri)
=======
                int(kwargs[ATTR_POSITION]), thingUri=self._thingUri)
>>>>>>> 203699105... Added Brunt Cover device
=======
                int(kwargs[ATTR_POSITION]), thingUri=self._thing_uri)
>>>>>>> 166484267... fixed some linting errors.
