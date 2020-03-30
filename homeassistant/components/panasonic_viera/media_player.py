"""Support for interface with a Panasonic Viera TV."""
import logging

from panasonic_viera import *
import voluptuous as vol
import wakeonlan

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_URL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

import pickle
from os import path

_LOGGER = logging.getLogger(__name__)

DOMAIN = "panasonic_viera"

CONF_APP_POWER = "app_power"

DEFAULT_NAME = "Panasonic Viera TV"
DEFAULT_PORT = 55000
DEFAULT_BROADCAST_ADDRESS = "255.255.255.255"
DEFAULT_APP_POWER = False

PANASONIC_VIERA_CONFIG_FILE = "panasonic_viera.conf"

TV_TYPE_NONENCRYPTED = 0
TV_TYPE_ENCRYPTED = 1

SUPPORT_VIERATV = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_STOP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MAC): cv.string,
        vol.Optional(
            CONF_BROADCAST_ADDRESS, default=DEFAULT_BROADCAST_ADDRESS
        ): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_APP_POWER, default=DEFAULT_APP_POWER): cv.boolean,
    }
)

SERVICE_SEND_KEY = "send_key"
ATTR_KEY = "key"

SEND_KEY_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids, vol.Required(ATTR_KEY): cv.string})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Panasonic Viera TV platform."""
    mac = config.get(CONF_MAC)
    broadcast = config.get(CONF_BROADCAST_ADDRESS)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)
    app_power = config.get(CONF_APP_POWER)

    if discovery_info:
        _LOGGER.debug("%s", discovery_info)
        name = discovery_info.get("name")
        host = discovery_info.get("host")
        port = discovery_info.get("port")
        udn = discovery_info.get("udn")
        if udn and udn.startswith("uuid:"):
            uuid = udn[len("uuid:") :]
        else:
            uuid = None
        remote = RemoteControl(host, port)
        add_entities([PanasonicVieraTVDevice(mac, name, remote, host, app_power, uuid)])
        return True

    host = config.get(CONF_HOST)
    remote = RemoteControl(host, port)

    if remote._type == TV_TYPE_ENCRYPTED:
        needs_pairing = True
        if path.exists(PANASONIC_VIERA_CONFIG_FILE):
            with open(PANASONIC_VIERA_CONFIG_FILE, "rb") as config_dict_file:
                config_dict = pickle.load(config_dict_file)
                if host in config_dict:
                    id = config_dict[host]["id"]
                    key = config_dict[host]["key"]

                    remote = RemoteControl(host, port, app_id=id, encryption_key=key)
                    needs_pairing = False

        if needs_pairing:
            configurator = hass.components.configurator

            async def pairing_callback(data):
                remote.request_pin_code()
                configurator.async_request_done(pairing_request)

                async def pin_callback(data):
                    try:
                        remote.authorize_pin_code(pincode=data["pin"])
                        configurator.async_request_done(pin_request)

                        config_dict = {host: {"id": remote._app_id, "key": remote._enc_key}}
                        with open(PANASONIC_VIERA_CONFIG_FILE, "wb") as config_dict_file:
                            pickle.dump(config_dict, config_dict_file)
                    except Exception as e:
                        _LOGGER.error(str(e))

                pin_request = configurator.async_request_config(
                    name,
                    pin_callback,
                    description="Enter the PIN code displayed on your TV.",
                    fields=[{"id": "pin", "name": "PIN"}],
                    submit_caption="Pair"
                )

            pairing_request = configurator.async_request_config(
                name,
                pairing_callback,
                description="Click start, reopen the configurator window and enter the PIN code displayed on your TV.",
                submit_caption="Start pairing request"
            )

    add_entities(
        [PanasonicVieraTVDevice(hass, mac, name, remote, host, broadcast, app_power)]
    )

    return True

class PanasonicVieraTVDevice(MediaPlayerDevice):
    """Representation of a Panasonic Viera TV."""

    def __init__(self, hass, mac, name, remote, host, broadcast, app_power, uuid=None):
        """Initialize the Panasonic device."""
        # Save a reference to the imported class
        self._wol = wakeonlan
        self._mac = mac
        self._name = name
        self._uuid = uuid
        self._muted = False
        self._playing = True
        self._state = None
        self._remote = remote
        self._host = host
        self._broadcast = broadcast
        self._volume = 0
        self._app_power = app_power

        hass.services.async_register(
            DOMAIN, SERVICE_SEND_KEY, self.send_key_handler, schema=SEND_KEY_SCHEMA
        )

    async def send_key_handler(self, service):
        key = service.data['key']
        self.send_key(Keys[key])

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this Viera TV."""
        return self._uuid

    def update(self):
        """Retrieve the latest data."""
        try:
            self._muted = self._remote.get_mute()
            self._volume = self._remote.get_volume() / 100
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF

        if self._remote._type == TV_TYPE_ENCRYPTED:
            self._remote = RemoteControl(self._remote._host, self._remote._port, app_id=self._remote._app_id, encryption_key=self._remote._enc_key)
        else:
            self._remote = RemoteControl(self._remote._host, self._remote._port)

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        try:
            self._remote.send_key(key)
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF
            return False
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mac or self._app_power:
            return SUPPORT_VIERATV | SUPPORT_TURN_ON
        return SUPPORT_VIERATV

    def turn_on(self):
        """Turn on the media player."""
        if self._mac:
            self._wol.send_magic_packet(self._mac, ip_address=self._broadcast)
            self._state = STATE_ON
        elif self._app_power:
            self._remote.turn_on()
            self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        if self._state != STATE_OFF:
            self._remote.turn_off()
            self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        self._remote.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._remote.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        self._remote.set_mute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume = int(volume * 100)
        try:
            self._remote.set_volume(volume)
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._remote.media_play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._remote.media_pause()

    def media_next_track(self):
        """Send next track command."""
        self._remote.media_next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        self._remote.media_previous_track()

    def play_media(self, media_type, media_id, **kwargs):
        """Play media."""
        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)

        if media_type == MEDIA_TYPE_URL:
            try:
                self._remote.open_webpage(media_id)
            except (TimeoutError, OSError):
                self._state = STATE_OFF
        else:
            _LOGGER.warning("Unsupported media_type: %s", media_type)

    def media_stop(self):
        """Stop playback."""
        self.send_key("NRC_CANCEL-ONOFF")
