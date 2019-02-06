"""
Support for EnOcean cover sources

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

SUPPORT_ENOCEAN = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ID, default=[]):
        vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def setup_platform(hass, config, add_devices, discovery_infom=None):
    """Set up the EnOcean Cover platform."""
    devname = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)
    add_devices([EnOceanCover(devname, dev_id)])

class EnOceanCover(enocean.EnOceanDevice, CoverDevice):
    """Representation of an EnOcean cover source."""

    def __init__(self, devname, dev_id):
        """Initialize the EnOcean cover source."""
        from enocean.protocol.packet import Packet
        from enocean.protocol.constants import PACKET, RORG

        enocean.EnOceanDevice.__init__(self)
        # self._sender_id = sender_id
        self.dev_id = dev_id
        self._devname = devname
        self.stype = "cover"
        self.percent_closed = 100
        self._is_opening = False
        self._is_closing = False

        self._async_on_done_timer = None

        self.send_packet(Packet.create(
            packet_type=PACKET.RADIO,
            rorg=RORG.VLD,
            rorg_func=0x05,
            rorg_type=0x00,
            destination=self.dev_id,
            sender=self.base_id,
            command=3
        ))

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return 100 - self.percent_closed

    def value_changed(self, value):
        """Update the current cover position and adjust all status of cover entity"""
        def on_done(a):
            """Called when timer throttle or percent determine close or opened"""
            self._is_closing = False
            self._is_opening = False
            self.schedule_update_ha_state()

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
        from enocean.protocol.packet import Packet
        from enocean.protocol.constants import PACKET, RORG
        self._is_opening = True
        self._is_closing = False

        self.send_packet(Packet.create(
            packet_type=PACKET.RADIO,
            rorg=RORG.VLD,
            rorg_func=0x05,
            rorg_type=0x00,
            destination=self.dev_id,
            sender=self.base_id,
            command=1,
            POS=0
        ))

    def close_cover(self, **kwargs):
        """Close cover."""
        from enocean.protocol.packet import Packet
        from enocean.protocol.constants import PACKET, RORG
        self._is_opening = False
        self._is_closing = True
        self.send_packet(Packet.create(
            packet_type=PACKET.RADIO,
            rorg=RORG.VLD,
            rorg_func=0x05,
            rorg_type=0x00,
            destination=self.dev_id,
            sender=self.base_id,
            command=1,
            POS=100
        ))

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        from enocean.protocol.packet import Packet
        from enocean.protocol.constants import PACKET, RORG
        position = kwargs.get(ATTR_POSITION)
        position = 100 - position

        if position < self.percent_closed:
            self._is_closing = False
            self._is_opening = True
        else:
            self._is_closing = True
            self._is_opening = False

        self.send_packet(Packet.create(
            packet_type=PACKET.RADIO,
            rorg=RORG.VLD,
            rorg_func=0x05,
            rorg_type=0x00,
            destination=self.dev_id,
            sender=self.base_id,
            command=1,
            POS=position
        ))

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