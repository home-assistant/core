"""Support for interface with a Sony Bravia TV."""
import ipaddress
import logging

from bravia_tv import BraviaRC
from getmac import get_mac_address
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

BRAVIA_CONFIG_FILE = "bravia.conf"

CLIENTID_PREFIX = "HomeAssistant"

DEFAULT_NAME = "Sony Bravia TV"

NICKNAME = "Home Assistant"

# Map ip to request id for configuring
_CONFIGURING = {}

_LOGGER = logging.getLogger(__name__)

SUPPORT_BRAVIA = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_STOP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sony Bravia TV platform."""
    host = config.get(CONF_HOST)

    if host is None:
        return

    pin = None
    bravia_config = load_json(hass.config.path(BRAVIA_CONFIG_FILE))
    while bravia_config:
        # Set up a configured TV
        host_ip, host_config = bravia_config.popitem()
        if host_ip == host:
            pin = host_config["pin"]
            mac = host_config["mac"]
            name = config.get(CONF_NAME)
            braviarc = BraviaRC(host, mac)
            braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
            unique_id = braviarc.get_system_info()["cid"].lower()

            add_entities([BraviaTVDevice(braviarc, name, pin, unique_id)])
            return

    setup_bravia(config, pin, hass, add_entities)


def setup_bravia(config, pin, hass, add_entities):
    """Set up a Sony Bravia TV based on host parameter."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    if pin is None:
        request_configuration(config, hass, add_entities)
        return

    try:
        if ipaddress.ip_address(host).version == 6:
            mode = "ip6"
        else:
            mode = "ip"
    except ValueError:
        mode = "hostname"
    mac = get_mac_address(**{mode: host})

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = hass.components.configurator
        configurator.request_done(request_id)
        _LOGGER.info("Discovery configuration done")

    # Save config
    save_json(
        hass.config.path(BRAVIA_CONFIG_FILE),
        {host: {"pin": pin, "host": host, "mac": mac}},
    )
    braviarc = BraviaRC(host, mac)
    braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
    unique_id = braviarc.get_system_info()["cid"].lower()

    add_entities([BraviaTVDevice(braviarc, name, pin, unique_id)])


def request_configuration(config, hass, add_entities):
    """Request configuration steps from the user."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    configurator = hass.components.configurator

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again."
        )
        return

    def bravia_configuration_callback(data):
        """Handle the entry of user PIN."""

        pin = data.get("pin")
        _braviarc = BraviaRC(host)
        _braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
        if _braviarc.is_connected():
            setup_bravia(config, pin, hass, add_entities)
        else:
            request_configuration(config, hass, add_entities)

    _CONFIGURING[host] = configurator.request_config(
        name,
        bravia_configuration_callback,
        description="Enter the Pin shown on your Sony Bravia TV."
        + "If no Pin is shown, enter 0000 to let TV show you a Pin.",
        description_image="/static/images/smart-tv.png",
        submit_caption="Confirm",
        fields=[{"id": "pin", "name": "Enter the pin", "type": ""}],
    )


class BraviaTVDevice(MediaPlayerDevice):
    """Representation of a Sony Bravia TV."""

    def __init__(self, client, name, pin, unique_id):
        """Initialize the Sony Bravia device."""

        self._pin = pin
        self._braviarc = client
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
        self._playing = False
        self._start_date_time = None
        self._program_media_type = None
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._unique_id = unique_id

        if self._braviarc.is_connected():
            self.update()
        else:
            self._state = STATE_OFF

    def update(self):
        """Update TV info."""
        if not self._braviarc.is_connected():
            if self._braviarc.get_power_status() != "off":
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
            if power_status == "active":
                self._state = STATE_ON
                playing_info = self._braviarc.get_playing_info()
                self._reset_playing_info()
                if playing_info is None or not playing_info:
                    self._channel_name = "App"
                else:
                    self._program_name = playing_info.get("programTitle")
                    self._channel_name = playing_info.get("title")
                    self._program_media_type = playing_info.get("programMediaType")
                    self._channel_number = playing_info.get("dispNum")
                    self._content_uri = playing_info.get("uri")
                    self._source = self._get_source()
                    self._duration = playing_info.get("durationSec")
                    self._start_date_time = playing_info.get("startDateTime")
            else:
                self._state = STATE_OFF

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error(exception_instance)
            self._state = STATE_OFF

    def _get_source(self):
        """Return the name of the source."""
        for key, value in self._content_mapping.items():
            if value == self._content_uri:
                return key

    def _reset_playing_info(self):
        self._program_name = None
        self._channel_name = None
        self._program_media_type = None
        self._channel_number = None
        self._source = None
        self._content_uri = None
        self._duration = None
        self._start_date_time = None

    def _refresh_volume(self):
        """Refresh volume information."""
        volume_info = self._braviarc.get_volume_info()
        if volume_info is not None:
            self._volume = volume_info.get("volume")
            self._min_volume = volume_info.get("minVolume")
            self._max_volume = volume_info.get("maxVolume")
            self._muted = volume_info.get("mute")

    def _refresh_channels(self):
        if not self._source_list:
            self._content_mapping = self._braviarc.load_source_list()
            self._source_list = []
            for key in self._content_mapping:
                self._source_list.append(key)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

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
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_BRAVIA

    @property
    def media_title(self):
        """Title of current playing media."""
        return_value = None
        if self._channel_name is not None:
            return_value = self._channel_name
            if self._program_name is not None:
                return_value = f"{return_value}: {self._program_name}"
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

    def media_stop(self):
        """Send media stop command to media player."""
        self._playing = False
        self._braviarc.media_stop()

    def media_next_track(self):
        """Send next track command."""
        self._braviarc.media_next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        self._braviarc.media_previous_track()
