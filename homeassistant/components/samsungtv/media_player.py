"""Support for interface with an Samsung TV."""
import asyncio
from datetime import timedelta
import socket

from samsungctl import Remote as SamsungRemote, exceptions as samsung_exceptions
import voluptuous as vol
import wakeonlan
from websocket import WebSocketException

from homeassistant.components.media_player import (
    DEVICE_CLASS_TV,
    PLATFORM_SCHEMA,
    MediaPlayerDevice,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .const import LOGGER

DEFAULT_NAME = "Samsung TV Remote"
DEFAULT_TIMEOUT = 1
DEFAULT_BROADCAST_ADDRESS = "255.255.255.255"

KEY_PRESS_TIMEOUT = 1.2
KNOWN_DEVICES_KEY = "samsungtv_known_devices"
METHODS = ("websocket", "legacy")
SOURCES = {"TV": "KEY_TV", "HDMI": "KEY_HDMI"}

SUPPORT_SAMSUNGTV = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_MAC): cv.string,
        vol.Optional(
            CONF_BROADCAST_ADDRESS, default=DEFAULT_BROADCAST_ADDRESS
        ): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Samsung TV platform."""
    known_devices = hass.data.get(KNOWN_DEVICES_KEY)
    if known_devices is None:
        known_devices = set()
        hass.data[KNOWN_DEVICES_KEY] = known_devices

    uuid = None
    # Is this a manual configuration?
    if config.get(CONF_HOST) is not None:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        name = config.get(CONF_NAME)
        mac = config.get(CONF_MAC)
        broadcast = config.get(CONF_BROADCAST_ADDRESS)
        timeout = config.get(CONF_TIMEOUT)
    elif discovery_info is not None:
        tv_name = discovery_info.get("name")
        model = discovery_info.get("model_name")
        host = discovery_info.get("host")
        name = f"{tv_name} ({model})"
        if name.startswith("[TV]"):
            name = name[4:]
        port = None
        timeout = DEFAULT_TIMEOUT
        mac = None
        broadcast = DEFAULT_BROADCAST_ADDRESS
        uuid = discovery_info.get("udn")
        if uuid and uuid.startswith("uuid:"):
            uuid = uuid[len("uuid:") :]

    # Only add a device once, so discovered devices do not override manual
    # config.
    ip_addr = socket.gethostbyname(host)
    if ip_addr not in known_devices:
        known_devices.add(ip_addr)
        add_entities([SamsungTVDevice(host, port, name, timeout, mac, broadcast, uuid)])
        LOGGER.info("Samsung TV %s added as '%s'", host, name)
    else:
        LOGGER.info("Ignoring duplicate Samsung TV %s", host)


class SamsungTVDevice(MediaPlayerDevice):
    """Representation of a Samsung TV."""

    def __init__(self, host, port, name, timeout, mac, broadcast, uuid):
        """Initialize the Samsung device."""

        # Save a reference to the imported classes
        self._name = name
        self._mac = mac
        self._broadcast = broadcast
        self._uuid = uuid
        # Assume that the TV is not muted
        self._muted = False
        # Assume that the TV is in Play mode
        self._playing = True
        self._state = None
        self._remote = None
        # Mark the end of a shutdown command (need to wait 15 seconds before
        # sending the next command to avoid turning the TV back ON).
        self._end_of_power_off = None
        # Generate a configuration for the Samsung library
        self._config = {
            "name": "HomeAssistant",
            "description": name,
            "id": "ha.component.samsung",
            "method": None,
            "port": port,
            "host": host,
            "timeout": timeout,
        }

        # Select method by port number, mainly for fallback
        if self._config["port"] in (8001, 8002):
            self._config["method"] = "websocket"
        elif self._config["port"] == 55000:
            self._config["method"] = "legacy"

    def update(self):
        """Update state of device."""
        self.send_key("KEY")

    def get_remote(self):
        """Create or return a remote control instance."""

        # Try to find correct method automatically
        if self._config["method"] not in METHODS:
            for method in METHODS:
                try:
                    self._config["method"] = method
                    LOGGER.debug("Try config: %s", self._config)
                    self._remote = SamsungRemote(self._config.copy())
                    self._state = STATE_ON
                    LOGGER.debug("Found working config: %s", self._config)
                    break
                except (
                    samsung_exceptions.UnhandledResponse,
                    samsung_exceptions.AccessDenied,
                ):
                    # We got a response so it's working.
                    self._state = STATE_ON
                    LOGGER.debug(
                        "Found working config without connection: %s", self._config
                    )
                    break
                except OSError as err:
                    LOGGER.debug("Failing config: %s error was: %s", self._config, err)
                    self._config["method"] = None

            # Unable to find working connection
            if self._config["method"] is None:
                self._remote = None
                self._state = None
                return None

        if self._remote is None:
            # We need to create a new instance to reconnect.
            self._remote = SamsungRemote(self._config.copy())

        return self._remote

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        if self._power_off_in_progress() and key not in ("KEY_POWER", "KEY_POWEROFF"):
            LOGGER.info("TV is powering off, not sending command: %s", key)
            return
        try:
            # recreate connection if connection was dead
            retry_count = 1
            for _ in range(retry_count + 1):
                try:
                    self.get_remote().control(key)
                    break
                except (
                    samsung_exceptions.ConnectionClosed,
                    BrokenPipeError,
                    WebSocketException,
                ):
                    # BrokenPipe can occur when the commands is sent to fast
                    # WebSocketException can occur when timed out
                    self._remote = None
            self._state = STATE_ON
        except AttributeError:
            # Auto-detect could not find working config yet
            pass
        except (samsung_exceptions.UnhandledResponse, samsung_exceptions.AccessDenied):
            # We got a response so it's on.
            self._state = STATE_ON
            self._remote = None
            LOGGER.debug("Failed sending command %s", key, exc_info=True)
            return
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            self._state = STATE_OFF
            self._remote = None
        if self._power_off_in_progress():
            self._state = STATE_OFF

    def _power_off_in_progress(self):
        return (
            self._end_of_power_off is not None
            and self._end_of_power_off > dt_util.utcnow()
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device."""
        return self._uuid

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source_list(self):
        """List of available input sources."""
        return list(SOURCES)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mac:
            return SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
        return SUPPORT_SAMSUNGTV

    @property
    def device_class(self):
        """Set the device class to TV."""
        return DEVICE_CLASS_TV

    def turn_off(self):
        """Turn off media player."""
        self._end_of_power_off = dt_util.utcnow() + timedelta(seconds=15)

        if self._config["method"] == "websocket":
            self.send_key("KEY_POWER")
        else:
            self.send_key("KEY_POWEROFF")
        # Force closing of remote session to provide instant UI feedback
        try:
            self.get_remote().close()
            self._remote = None
        except OSError:
            LOGGER.debug("Could not establish connection.")

    def volume_up(self):
        """Volume up the media player."""
        self.send_key("KEY_VOLUP")

    def volume_down(self):
        """Volume down media player."""
        self.send_key("KEY_VOLDOWN")

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_key("KEY_MUTE")

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self.send_key("KEY_PLAY")

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self.send_key("KEY_PAUSE")

    def media_next_track(self):
        """Send next track command."""
        self.send_key("KEY_CHUP")

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_key("KEY_CHDOWN")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        if media_type != MEDIA_TYPE_CHANNEL:
            LOGGER.error("Unsupported media type")
            return

        # media_id should only be a channel number
        try:
            cv.positive_int(media_id)
        except vol.Invalid:
            LOGGER.error("Media ID must be positive integer")
            return

        for digit in media_id:
            await self.hass.async_add_job(self.send_key, f"KEY_{digit}")
            await asyncio.sleep(KEY_PRESS_TIMEOUT, self.hass.loop)
        await self.hass.async_add_job(self.send_key, "KEY_ENTER")

    def turn_on(self):
        """Turn the media player on."""
        if self._mac:
            wakeonlan.send_magic_packet(self._mac, ip_address=self._broadcast)
        else:
            self.send_key("KEY_POWERON")

    async def async_select_source(self, source):
        """Select input source."""
        if source not in SOURCES:
            LOGGER.error("Unsupported source")
            return

        await self.hass.async_add_job(self.send_key, SOURCES[source])
