"""
Support for EnOcean cover sources.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.enocean/
"""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_STOP,
    ATTR_POSITION,
    PLATFORM_SCHEMA
)
from homeassistant.const import (CONF_NAME, CONF_ID)
from homeassistant.components import enocean
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_ID = 'sender_id'

DEFAULT_NAME = 'EnOcean Cover'
DEPENDENCIES = ['enocean']

SUPPORT_ENOCEAN = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ID, default=[]):
        vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_infom=None):
    """Set up the EnOcean Cover platform."""
    dev_name = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)
    add_entities([EnOceanCover(dev_name, dev_id)])

class EnOceanCover(enocean.EnOceanDevice, CoverDevice):
    """Representation of an EnOcean cover source."""

    def __init__(self, dev_name, dev_id):
        """Initialize the EnOcean cover source."""
        super().__init__(dev_id, dev_name)
        self.percent_closed = 100
        self._is_opening = False
        self._is_closing = False

        self._async_on_done_timer = None

#        optional = [0x03, ]
#        optional.extend(self.dev_id)
#        optional.extend([0xFF, 0x00])

#        data = [0xD2, 0x03]
#        data.extend(self.base_id)
#        data.extend([0x00])
        
#        self.send_command(data=data, optional=optional,packet_type=0x01)

    @property
    def name(self):
        """Return the device name."""
        return self.dev_name

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return 100 - self.percent_closed

    def value_changed(self, packet):
        """Update the current cover position.

        And adjust all status of cover entity
        """
        def on_done(time):
            """Reset opening/closing status."""
            self._is_closing = False
            self._is_opening = False
            self.schedule_update_ha_state()
        
        _LOGGER.warning("Received radio packet COVER : %s", packet)
        if packet.data[0] == 0xd2:
            # actuator status telegram
            packet.parse_eep(0x05, 0x00)
            if packet.parsed['CMD']['raw_value'] == 4:
                _LOGGER.warning("Received parsed: %s", packet.parsed)
                value = packet.parsed['POS']['raw_value']
                self.percent_closed = value
                if self._async_on_done_timer:
                	self._async_on_done_timer()
                if self.percent_closed <= 0 or self.percent_closed >= 100:
                	on_done(None)
                else:
                	self._async_on_done_timer = async_call_later(self.hass, 3, on_done)
                self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ENOCEAN

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._is_opening = True
        self._is_closing = False

        optional = [0x03, ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])

        data = [0xD2, 0x00, 0x00, 0x00, 0x01]
        data.extend(self.base_id)
        data.extend([0x00])
        
        self.send_command(data=data, optional=optional,packet_type=0x01)
        
    def close_cover(self, **kwargs):
        """Close cover."""
        self._is_opening = False
        self._is_closing = True

        optional = [0x03, ]
        optional.extend(self.dev_id)
        optional.extend([0xff, 0x00])
        
        data = [0xD2, 0x64, 0x00, 0x00, 0x01]
        data.extend(self.base_id)
        data.extend([0x00])
        
        self.send_command(data=data, optional=optional,packet_type=0x01)

    def stop_cover(self, **kwargs):
        """Stop cover."""
        
        optional = [0x03, ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])

        data = [0xD2, 0x02]
        data.extend(self.base_id)
        data.extend([0x00])
        
        self.send_command(data=data, optional=optional,packet_type=0x01)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        position = 100 - position

        if position < self.percent_closed:
            self._is_closing = False
            self._is_opening = True
        else:
            self._is_closing = True
            self._is_opening = False

        optional = [0x03, ]
        optional.extend(self.dev_id)
        optional.extend([0xff, 0x00])

        data = [0xD2, ]
        data.extend([position])
        data.extend([0x00, 0x00, 0x01])
        data.extend(self.base_id)
        data.extend([0x00])

        self.send_command(data=data, optional=optional,packet_type=0x01)

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self.percent_closed == 100
