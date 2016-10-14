"""
Support for interface with a Sony Bravia TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.braviatv/
"""
import logging
import os
import json
import re

import voluptuous as vol

from homeassistant.loader import get_component
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_SET, SUPPORT_SELECT_SOURCE, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/aparraga/braviarc/archive/0.3.5.zip'
    '#braviarc==0.3.5']

BRAVIA_CONFIG_FILE = 'bravia.conf'

CLIENTID_PREFIX = 'HomeAssistant'

DEFAULT_NAME = 'Sony Bravia TV'

NICKNAME = 'Home Assistant'

# Map ip to request id for configuring
_CONFIGURING = {}

_LOGGER = logging.getLogger(__name__)

SUPPORT_BRAVIA = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
                 SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                 SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
                 SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def _get_mac_address(ip_address):
    """Get the MAC address of the device."""
    from subprocess import Popen, PIPE

    pid = Popen(["arp", "-n", ip_address], stdout=PIPE)
    pid_component = pid.communicate()[0]
    match = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})".encode('UTF-8'),
                      pid_component)
    if match is not None:
        return match.groups()[0]
    else:
        return None


def _config_from_file(filename, config=None):
    """Create the configuration from a file."""
    if config:
        # We're writing configuration
        bravia_config = _config_from_file(filename)
        if bravia_config is None:
            bravia_config = {}
        new_config = bravia_config.copy()
        new_config.update(config)
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(new_config))
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except ValueError as error:
                return {}
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Sony Bravia TV platform."""
    host = config.get(CONF_HOST)

    if host is None:
        return  # if no host configured, do not continue

    pin = None
    bravia_config = _config_from_file(hass.config.path(BRAVIA_CONFIG_FILE))
    while len(bravia_config):
        # Setup a configured TV
        host_ip, host_config = bravia_config.popitem()
        if host_ip == host:
            pin = host_config['pin']
            mac = host_config['mac']
            name = config.get(CONF_NAME)
            add_devices([BraviaTVDevice(host, mac, name, pin)])
            return

    setup_bravia(config, pin, hass, add_devices)


# pylint: disable=too-many-branches
def setup_bravia(config, pin, hass, add_devices):
    """Setup a Sony Bravia TV based on host parameter."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    if pin is None:
        request_configuration(config, hass, add_devices)
        return
    else:
        mac = _get_mac_address(host)
        if mac is not None:
            mac = mac.decode('utf8')
        # If we came here and configuring this host, mark as done
        if host in _CONFIGURING:
            request_id = _CONFIGURING.pop(host)
            configurator = get_component('configurator')
            configurator.request_done(request_id)
            _LOGGER.info('Discovery configuration done!')

        # Save config
        if not _config_from_file(
                hass.config.path(BRAVIA_CONFIG_FILE),
                {host: {'pin': pin, 'host': host, 'mac': mac}}):
            _LOGGER.error('failed to save config file')

        add_devices([BraviaTVDevice(host, mac, name, pin)])


def request_configuration(config, hass, add_devices):
    """Request configuration steps from the user."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again.")
        return

    def bravia_configuration_callback(data):
        """Callback after user enter PIN."""
        from braviarc import braviarc

        pin = data.get('pin')
        braviarc = braviarc.BraviaRC(host)
        braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
        if braviarc.is_connected():
            setup_bravia(config, pin, hass, add_devices)
        else:
            request_configuration(config, hass, add_devices)

    _CONFIGURING[host] = configurator.request_config(
        hass, name, bravia_configuration_callback,
        description='Enter the Pin shown on your Sony Bravia TV.' +
        'If no Pin is shown, enter 0000 to let TV show you a Pin.',
        description_image="/static/images/smart-tv.png",
        submit_caption="Confirm",
        fields=[{'id': 'pin', 'name': 'Enter the pin', 'type': ''}]
    )


# pylint: disable=abstract-method, too-many-public-methods,
# pylint: disable=too-many-instance-attributes, too-many-arguments
class BraviaTVDevice(MediaPlayerDevice):
    """Representation of a Sony Bravia TV."""

    def __init__(self, host, mac, name, pin):
        """Initialize the Sony Bravia device."""
        from braviarc import braviarc

        self._pin = pin
        self._braviarc = braviarc.BraviaRC(host, mac)
        self._name = name
        self._state = STATE_OFF
        self._muted = False
        self._program_name = None
        self._channel_name = None
        self._channel_number = None
        self._source = None
        self._source_list = []
        self._original_content_list = []
        self._content_mapping = {}
        self._duration = None
        self._content_uri = None
        self._id = None
        self._playing = False
        self._start_date_time = None
        self._program_media_type = None
        self._min_volume = None
        self._max_volume = None
        self._volume = None

        self._braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
        if self._braviarc.is_connected():
            self.update()
        else:
            self._state = STATE_OFF

    def update(self):
        """Update TV info."""
        if not self._braviarc.is_connected():
            self._braviarc.connect(self._pin, CLIENTID_PREFIX, NICKNAME)
            if not self._braviarc.is_connected():
                return

        # Retrieve the latest data.
        try:
            if self._state == STATE_ON:
                # refresh volume info:
                self._refresh_volume()
                self._refresh_channels()

            power_status = self._braviarc.get_power_status()
            if power_status == 'active':
                self._state = STATE_ON
                playing_info = self._braviarc.get_playing_info()
                if playing_info is None or len(playing_info) == 0:
                    self._channel_name = 'App'
                else:
                    self._program_name = playing_info.get('programTitle')
                    self._channel_name = playing_info.get('title')
                    self._program_media_type = playing_info.get(
                        'programMediaType')
                    self._channel_number = playing_info.get('dispNum')
                    self._source = playing_info.get('source')
                    self._content_uri = playing_info.get('uri')
                    self._duration = playing_info.get('durationSec')
                    self._start_date_time = playing_info.get('startDateTime')
            else:
                self._state = STATE_OFF

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error(exception_instance)
            self._state = STATE_OFF

    def _refresh_volume(self):
        """Refresh volume information."""
        volume_info = self._braviarc.get_volume_info()
        if volume_info is not None:
            self._volume = volume_info.get('volume')
            self._min_volume = volume_info.get('minVolume')
            self._max_volume = volume_info.get('maxVolume')
            self._muted = volume_info.get('mute')

    def _refresh_channels(self):
        if len(self._source_list) == 0:
            self._content_mapping = self._braviarc. \
                load_source_list()
            self._source_list = []
            for key in self._content_mapping:
                self._source_list.append(key)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is not None:
            return self._volume / 100
        else:
            return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_BRAVIA

    @property
    def media_title(self):
        """Title of current playing media."""
        return_value = None
        if self._channel_name is not None:
            return_value = self._channel_name
            if self._program_name is not None:
                return_value = return_value + ': ' + self._program_name
        return return_value

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._channel_name

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._duration

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._braviarc.set_volume_level(volume)

    def turn_on(self):
        """Turn the media player on."""
        self._braviarc.turn_on()

    def turn_off(self):
        """Turn off media player."""
        self._braviarc.turn_off()

    def volume_up(self):
        """Volume up the media player."""
        self._braviarc.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._braviarc.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        self._braviarc.mute_volume(mute)

    def select_source(self, source):
        """Set the input source."""
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            self._braviarc.play_content(uri)

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._braviarc.media_play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._braviarc.media_pause()

    def media_next_track(self):
        """Send next track command."""
        self._braviarc.media_next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        self._braviarc.media_previous_track()
