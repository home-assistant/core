"""Support for interface with an Samsung TV."""
import socket
from typing import Optional
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice, PLATFORM_SCHEMA
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
from homeassistant.components.ssdp import (
    ATTR_HOST,
    ATTR_NAME,
    ATTR_MODEL_NAME,
    ATTR_UDN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .const import CONF_MANUFACTURER, CONF_MODEL, DOMAIN, LOGGER


DEFAULT_NAME = "Samsung TV Remote"
DEFAULT_TIMEOUT = 1

KEY_PRESS_TIMEOUT = 1.2
KNOWN_DEVICES_KEY = "samsungtv_known_devices"
SOURCES = {"TV": "KEY_TV", "HDMI": "KEY_HDMI"}
AVAILABLE_METHODS = ("websocket", "legacy")

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
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Samsung TV platform."""
    known_devices = hass.data.get(KNOWN_DEVICES_KEY)
    if known_devices is None:
        known_devices = set()
        hass.data[KNOWN_DEVICES_KEY] = known_devices

    port = None
    timeout = DEFAULT_TIMEOUT
    mac = None
    uuid = None
    # Is this a manual configuration?
    if config.get(CONF_HOST) is not None:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        name = config.get(CONF_NAME)
        mac = config.get(CONF_MAC)
        timeout = config.get(CONF_TIMEOUT)
    elif discovery_info is not None:
        tv_name = discovery_info.get(ATTR_NAME)
        model = discovery_info.get(ATTR_MODEL_NAME)
        host = discovery_info.get(ATTR_HOST)
        udn = discovery_info.get(ATTR_UDN)
        if udn and udn.startswith("uuid:"):
            uuid = udn[len("uuid:") :]
        if tv_name.startswith("[TV]"):
            tv_name = tv_name[4:]
        name = "{} ({})".format(tv_name, model)
    else:
        LOGGER.warning("Cannot determine device")
        return

    # Only add a device once, so discovered devices do not override manual
    # config.
    ip_addr = socket.gethostbyname(host)
    if ip_addr not in known_devices:
        known_devices.add(ip_addr)
        async_add_devices([SamsungTVDevice(host, port, name, timeout, mac, uuid)])
    else:
        LOGGER.info("Ignoring duplicate Samsung TV %s", host)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Samsung TV from a config entry."""
    known_devices = hass.data.get(KNOWN_DEVICES_KEY)
    if known_devices is None:
        known_devices = set()
        hass.data[KNOWN_DEVICES_KEY] = known_devices

    host = config_entry.data[CONF_HOST]
    port = None
    name = config_entry.title
    timeout = DEFAULT_TIMEOUT
    mac = None
    uuid = config_entry.data[CONF_ID]
    manufacturer = config_entry.data[CONF_MANUFACTURER]
    model = config_entry.data[CONF_MODEL]

    # Only add a device once, so discovered devices do not override manual
    # config.
    ip_addr = socket.gethostbyname(host)
    if ip_addr not in known_devices:
        known_devices.add(ip_addr)
        async_add_devices(
            [SamsungTVDevice(host, port, name, timeout, mac, uuid, manufacturer, model)]
        )
    else:
        LOGGER.info("Ignoring duplicate Samsung TV %s", host)


class SamsungTVDevice(MediaPlayerDevice):
    """Representation of a Samsung TV."""

    def __init__(
        self, host, port, name, timeout, mac, uuid, manufacturer=None, model=None
    ):
        """Initialize the Samsung device."""
        self._name = name
        self._host = host
        self._port = port
        self._mac = mac
        self._uuid = uuid
        self._manufacturer = manufacturer
        self._model = model
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

        self._get_remote()

    def update(self):
        """Update state of device."""
        self._get_remote(True)

    def _get_remote(self, clean=False):
        """Create or return a remote control instance."""
        from samsungctl import Remote, exceptions

        # Select method by port number, mainly for fallback
        if self._config["port"] in (8001, 8002):
            self._config["method"] = "websocket"
        elif self._config["port"] == 55000:
            self._config["method"] = "legacy"

        # Try to find correct method automatically
        elif self._config["method"] not in AVAILABLE_METHODS:
            for method in AVAILABLE_METHODS:
                try:
                    self._config["method"] = method
                    self._remote = Remote(self._config.copy())
                    self._state = STATE_ON
                    LOGGER.debug("found working config: %s", self._config)
                    break
                except Exception:
                    self._config["method"] = None

            # Unable to find working connection
            if self._config["method"] is None:
                self._remote = None
                self._state = STATE_UNKNOWN
                return None

        # Close existing connection
        if clean and self._remote is not None:
            self._remote.close()
            self._remote = None

        # We need to create a new instance to reconnect
        if self._remote is None:
            try:
                self._remote = Remote(self._config)
                self._state = STATE_ON
            except (exceptions.UnhandledResponse, exceptions.AccessDenied):
                # We got a response so it's on
                self._remote = None
                self._state = STATE_ON
            except (exceptions.ConnectionClosed, OSError):
                self._remote = None
                self._state = STATE_OFF

        return self._remote

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        if self._power_off_in_progress() and key not in ("KEY_POWER", "KEY_POWEROFF"):
            LOGGER.info("TV is powering off, not sending command: %s", key)
            return

        # recreate connection if connection was dead
        retry_count = 1
        for _ in range(retry_count + 1):
            try:
                self._get_remote().control(key)
                break
            except Exception:
                LOGGER.debug("Failed sending command %s", key, exc_info=True)
                self._remote = None

    def _power_off_in_progress(self):
        return (
            self._end_of_power_off is not None
            and self._end_of_power_off > dt_util.utcnow()
        )

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._uuid

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._state

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": self._manufacturer,
            "model": self._model,
        }

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

    def turn_off(self):
        """Turn off media player."""
        from datetime import timedelta

        self._end_of_power_off = dt_util.utcnow() + timedelta(seconds=15)

        if self._config["method"] == "websocket":
            self.send_key("KEY_POWER")
        else:
            self.send_key("KEY_POWEROFF")
        # Force closing of remote session to provide instant UI feedback
        try:
            self._get_remote().close()
            self._remote = None
        except Exception:
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
        self.send_key("KEY_FF")

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_key("KEY_REWIND")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        import asyncio
        import voluptuous as vol
        import homeassistant.helpers.config_validation as cv

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
            await self.hass.async_add_job(self.send_key, "KEY_" + digit)
            await asyncio.sleep(KEY_PRESS_TIMEOUT, self.hass.loop)
        await self.hass.async_add_job(self.send_key, "KEY_ENTER")

    def turn_on(self):
        """Turn the media player on."""
        import wakeonlan

        if self._mac:
            wakeonlan.send_magic_packet(self._mac)
        else:
            self.send_key("KEY_POWERON")

    async def async_select_source(self, source):
        """Select input source."""
        if source not in SOURCES:
            LOGGER.error("Unsupported source")
            return

        await self.hass.async_add_job(self.send_key, SOURCES[source])
