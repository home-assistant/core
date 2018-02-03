"""
Provide functionality to interact with Wink Relay devices on the network.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.wink_relay/
"""
import logging

import voluptuous as vol
import requests

from homeassistant.components.media_player import (
    SUPPORT_PLAY_MEDIA, MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC,
    DOMAIN)
from homeassistant.const import (CONF_NAME, STATE_IDLE, CONF_HOST,
                                 STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pywinkrelayintercom==0.0.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'wink_relay_intercom'
DEFAULT_CONVERT = False
CONF_NETMASK = 'netmask'
CONF_AUDIO_BOOST = 'audio_boost'
CONF_CONVERT = 'convert'

SERVICE_ACTIVATE_INTERCOM = "wink_relay_activate_intercom"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NETMASK): cv.string,
    vol.Optional(CONF_AUDIO_BOOST): cv.positive_int,
    vol.Optional(CONF_CONVERT, DEFAULT_CONVERT): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink Relay intercom platform."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME, DEFAULT_NAME)
    netmask = config.get(CONF_NETMASK)
    audio_boost = config.get(CONF_AUDIO_BOOST)
    convert = config.get(CONF_CONVERT)
    intercom = WinkRelayIntercom(name, host, netmask, audio_boost, convert)
    hass.data[DEFAULT_NAME] = intercom
    add_devices([intercom])

    def activate_intercom(call):
        """
        Start listening for SSDP request from Intercom.

        This only needs called once for users that only have one
        relay on their network.
        """
        hass.data[DEFAULT_NAME].activate_intercom()

    hass.services.register(DOMAIN, SERVICE_ACTIVATE_INTERCOM, activate_intercom)


class WinkRelayIntercom(MediaPlayerDevice):
    """Representation of a Wink Relay intercom."""

    def __init__(self, name, host, netmask, audio_boost, convert):
        """Initialize the vlc device."""
        from winkrelayintercom import WinkRelayIntercomBroadcaster

        self._broadcaster = WinkRelayIntercomBroadcaster(host, netmask,
                                                         convert, audio_boost)
        self._name = name
        self._state = STATE_IDLE

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_PLAY_MEDIA

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if not media_type == MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type, MEDIA_TYPE_MUSIC)
            return
        self._state = STATE_PLAYING
        self._broadcaster.send_audio(data=_download_file(media_id))
        self._state = STATE_IDLE

    def activate_intercom(self):
        """Call to the broadcaster to start listening for SSDP."""
        self._broadcaster.activate_relay_intercom()


def _download_file(url):
    _request = requests.get(url, stream=True)
    return _request.content
