"""
Support for Brunt Blind Engine covers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cover/brunt
"""
import logging
import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_SET_POSITION,
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
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['brunt==0.1.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'brunt'
ATTRIBUTION = 'Based on an unofficial Brunt SDK.'

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

ATTR_COVER_STATE = 'cover_state'
ATTR_CURRENT_POSITION = 'current_position'
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
})


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
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the brunt platform."""
>>>>>>> 203699105... Added Brunt Cover device
    from brunt import BruntAPI
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    bapi = BruntAPI(username=username, password=password)
    try:
        things = bapi.getThings()['things']
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
    def __init__(self, hass, bapi, name, thing_uri):
        """Init the Brunt device."""
        self._bapi = bapi
        self._name = name
        self._thing_uri = thing_uri
=======
    def __init__(self, hass, bapi, name, thingUri):
        """Init the Brunt device."""
        # from brunt import BruntAPI
        self._bapi = bapi
        self._name = name
        self._thingUri = thingUri
>>>>>>> 203699105... Added Brunt Cover device

        self._state = None
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

    @property
    def state(self):
        """Return the state of the cover."""
        return STATE_CLOSED if int(
            self._state['currentPosition']) == CLOSED_POSITION else STATE_OPEN

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
                thingUri=self._thing_uri)['thing']
=======
                thingUri=self._thingUri)['thing']
>>>>>>> 203699105... Added Brunt Cover device
            self._available = True
        except (TypeError, KeyError, NameError, ValueError) as ex:
            _LOGGER.error("%s", ex)
            self._available = False

    def open_cover(self, **kwargs):
        """ set the cover to the open position. """
        self._bapi.changeRequestPosition(
<<<<<<< HEAD
            OPEN_POSITION, thingUri=self._thing_uri)
=======
            OPEN_POSITION, thingUri=self._thingUri)

<<<<<<< HEAD
>>>>>>> 203699105... Added Brunt Cover device

=======
>>>>>>> 64ddfcc80... small styling updates
    def close_cover(self, **kwargs):
        """ set the cover to the closed position. """
        self._bapi.changeRequestPosition(
<<<<<<< HEAD
            CLOSED_POSITION, thingUri=self._thing_uri)
=======
            CLOSED_POSITION, thingUri=self._thingUri)
>>>>>>> 203699105... Added Brunt Cover device

    def set_cover_position(self, **kwargs):
        """ set the cover to a specific position. """
        if ATTR_POSITION in kwargs:
            self._bapi.changeRequestPosition(
<<<<<<< HEAD
                int(kwargs[ATTR_POSITION]), thingUri=self._thing_uri)
=======
                int(kwargs[ATTR_POSITION]), thingUri=self._thingUri)
>>>>>>> 203699105... Added Brunt Cover device
