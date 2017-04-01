"""
Support for NAD D 7050 digital amplifier.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.nad7050/
"""
import logging
import codecs
import socket
from time import sleep
import voluptuous as vol
from homeassistant.components.media_player import (
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'NAD D 7050'
DEFAULT_MIN_VOLUME = -60
DEFAULT_MAX_VOLUME = -10
DEFAULT_VOLUME_STEP = 2

SUPPORT_NAD = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | \
              SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | SUPPORT_SELECT_SOURCE

CONF_MIN_VOLUME = 'min_volume'
CONF_MAX_VOLUME = 'max_volume'
CONF_VOLUME_STEP = 'volume_step'
CONF_HOST = 'host'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): int,
    vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): int,
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the NAD platform."""
    add_devices([NAD7050(
        config.get(CONF_HOST),
        config.get(CONF_NAME),
        config.get(CONF_MIN_VOLUME),
        config.get(CONF_MAX_VOLUME),
        config.get(CONF_VOLUME_STEP),
    )])


class NAD7050(MediaPlayerDevice):
    """Representation of a NAD D 7050 device."""

    def __init__(self, host, name, min_volume, max_volume, volume_step):
        """Initialize the amplifier."""
        self._name = name
        self._host = host
        self._port = 50001
        self._buffersize = 1024
        self._min_volume = (min_volume + 90) * 2  # conversion to nad vol range
        self._max_volume = (max_volume + 90) * 2  # conversion to nad vol range
        self._volume_step = volume_step
        self._state = None
        self._mute = None
        self._volume = None
        self._source = None
        self._source_mapping = {'00': 'Coaxial 1', '01': 'Coaxial 2',
                                '02': 'Optical 1', '03': 'Optical 2',
                                '04': 'Computer', '05': 'Airplay',
                                '06': 'Dock', '07': 'Bluetooth'}
        self._source_list = list(self._source_mapping.values())
        self._reverse_mapping = \
            {value: key for key, value in self._source_mapping.items()}

        self.update()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest details from the device."""
        query_all = \
            "000102020400010202060001020207000102020800010202050001020209" \
            "000102020a000102020c0001020203000102020d00010207000001020800"

        nad_reply = self.send(query_all, read_reply=True)
        if nad_reply is None:
            return
        nad_reply = codecs.encode(nad_reply, 'hex').decode("utf-8")

        # split reply into parts of 10 characters
        num_chars = 10
        nad_status = [nad_reply[i:i + num_chars]
                      for i in range(0, len(nad_reply), num_chars)]
        logging.debug(nad_status)
        volume = int(nad_status[0][-2:], 16)  # converts 2B hex value to int
        power = nad_status[5][-2:]
        mute = nad_status[6][-2:]
        source = nad_status[7][-2:]

        # Update current volume
        self._volume = self.nad_volume_to_internal_volume(volume)

        # Update muted state
        self._mute = bool(mute == '01')

        # Update on/off state
        if power == '01':
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

        # Update current source
        self._source = self._source_mapping[source]
        logging.debug("Updated source to %s" % self._source)

    def nad_volume_to_internal_volume(self, nad_volume):
        """Convert nad volume range (0-200) to internal volume range.

        Takes into account configured min and max volume.
        """
        if nad_volume < self._min_volume:
            volume_internal = 0.0
        if nad_volume > self._max_volume:
            volume_internal = 1.0
        else:
            volume_internal = (nad_volume - self._min_volume) / \
                              (self._max_volume - self._min_volume)
        logging.debug("updating volume to %i" % volume_internal)
        return volume_internal

    def send(self, message, read_reply=False):
        """Send a command string to the amplifier."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self._host, self._port))
        except ConnectionError:
            return
        message = codecs.decode(message, 'hex_codec')
        sock.send(message)
        sleep(0.5)
        if read_reply:
            reply = sock.recv(self._buffersize)
            sock.close()
            return reply
        sock.close()
        sleep(1)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_NAD

    def turn_off(self):
        """Turn the media player off."""
        self.send('00010207000001020207')  # Power save off
        self.send('0001020900')  # Device off

    def turn_on(self):
        """Turn the media player on."""
        self.send('0001020901')

    def volume_up(self):
        """Step volume up in the configured increments."""
        volume_step = self._volume_to_step()
        self.set_volume_level(self._volume + volume_step)

    def volume_down(self):
        """Step volume down in the configured increments."""
        volume_step = self._volume_to_step()
        self.set_volume_level(self._volume - volume_step)

    def _volume_to_step(self):
        """Convert configured volume_step into internal volume delta."""
        return self._volume_step * 2 / (self._max_volume - self._min_volume)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        nad_volume_to_set = \
            int(round(volume * (self._max_volume - self._min_volume) +
                      self._min_volume))
        self.send('00010204{}'.format(format(nad_volume_to_set, "02x")))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.send('0001020a01')
        else:
            self.send('0001020a00')

    def select_source(self, source):
        """Select input source."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self.send('00010203' + source)

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute
