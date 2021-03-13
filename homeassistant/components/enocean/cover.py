"""Support for EnOcean cover sources."""

import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    CoverEntity,
    SUPPORT_SET_POSITION)

from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    STATE_CLOSED)

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.event as ev

from .device import EnOceanEntity

CONF_SENDER_ID = "sender_id"
CONF_DRIVING_TIME = "driving_time"

DEFAULT_NAME = "EnOcean Shutter"
DEFAULT_NAME = "Enocean Cover"
DEFAULT_DRIVING_TIME = 999
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PAYLOAD_STOP = "STOP"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
    vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DRIVING_TIME, default=DEFAULT_DRIVING_TIME): vol.All(cv.ensure_list, [vol.Coerce(int)])})

def setup_platform(hass, config, add_entities, discovery_info=None):


    """Set up the EnOcean cover platform."""
    sender_id = config.get(CONF_SENDER_ID)
    dev_name = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)
    driving_time = config.get(CONF_DRIVING_TIME)

    add_entities([EnOceanCover(sender_id, dev_id, dev_name, driving_time)])


class EnOceanCover(EnOceanEntity, CoverEntity):
    """Representation of an EnOcean cover source."""

    def __init__(self, sender_id, dev_id, dev_name, driving_time):
        """Initialize the EnOcean cover source."""
        super().__init__(dev_id, dev_name)
        self._sender_id = sender_id
        self._driving_time = driving_time[0] * 10 
        self._state = None
        self._last_command = None
        self._position = None

    @property
    def supported_features(self):

        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def is_closed(self):
        """Return true if the cover is closed or None if the status is unknown."""
        if self._state is None:
            return None

        return self._state == STATE_CLOSED

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.dev_name

    def open_cover(self):
        """Set the up command for shutter on Eltako FSB14"""
        self._last_command = 0x70
        command = [0xF6, 0x70]
        command.extend(self._sender_id)
        command.extend([0x30])
        self.send_command(command, [0x0, 0xFF, 0xFF], 0x01)

    def close_cover(self):
        """Set the down command for shutter on Eltako FSB14"""
        self._last_command = 0x50
        command = [0xF6, 0x50]
        command.extend(self._sender_id)
        command.extend([0x30])
        self.send_command(command, [0x0, 0xFF, 0xFF], 0x01)
        
    def stop_cover(self):
        """Send either close or open command one time more for stop
        and calculates Shutter position"""
        if self._last_command == 0x70:
            command =  [0xF6, 0x70]
        elif self._last_command == 0x50:
            command =  [0xF6, 0x50]
        else:
            return
        self._last_command = None
        command.extend(self._sender_id)
        command.extend([0x30])
        self.send_command(command, [0x0, 0xFF, 0xFF], 0x01)

    def set_cover_position(self,position):
        """ Set cover position in widget. This is the cheap realization with timeouts.
        in future you should find out the correct command for GFVS driving command
        telegram and teach in telegram."""
        drive_time = int(abs(position - self._position) * self._driving_time/100)
        if self._position < position: #Open cover
            self.open_cover()
            ev.async_call_later(self.hass, drive_time/10, lambda _:self.stop_cover())
        elif self._position > position: #Close cover
            self.close_cover()
            ev.async_call_later(self.hass, drive_time/10, lambda _:self.stop_cover())

    def value_changed(self, packet):
        """For Handling if Shutter is started from external trigger
        """
        
        if packet.data[1] == 0x00:
            driven_time = packet.data[2]
            percentage = int(100 * driven_time /self._driving_time)
            if packet.data[3] == 0x01: 
                #open
                self._position += percentage
            elif packet.data[3] == 0x02: 
                #close
                self._position -= percentage
        elif packet.data[1] == 0x70:
            self._position = 100
        elif packet.data[1] == 0x50:
            self._position = 0
        self.schedule_update_ha_state()
