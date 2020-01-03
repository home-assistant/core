"""Support for interface with an Samsung TV."""
import asyncio
from datetime import timedelta

from samsungctl import Remote as SamsungRemote, exceptions as samsung_exceptions
import voluptuous as vol
from websocket import WebSocketException

from homeassistant.components.media_player import DEVICE_CLASS_TV, MediaPlayerDevice
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
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_ON_ACTION,
    DOMAIN,
    LOGGER,
    METHODS,
)

KEY_PRESS_TIMEOUT = 1.2
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


async def async_setup_platform(
    hass, config, add_entities, discovery_info=None
):  # pragma: no cover
    """Set up the Samsung TV platform."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Samsung TV from a config entry."""
    host = config_entry.data[CONF_HOST]
    manufacturer = config_entry.data.get(CONF_MANUFACTURER)
    model = config_entry.data.get(CONF_MODEL)
    name = config_entry.title
    port = config_entry.data.get(CONF_PORT)
    uuid = config_entry.data.get(CONF_ID)
    turn_on_action = config_entry.data.get(CONF_ON_ACTION)
    on_script = Script(hass, turn_on_action) if turn_on_action else None

    async_add_entities(
        [SamsungTVDevice(host, port, name, uuid, manufacturer, model, on_script)]
    )


class SamsungTVDevice(MediaPlayerDevice):
    """Representation of a Samsung TV."""

    def __init__(
        self, host, port, name, uuid, manufacturer=None, model=None, on_script=None,
    ):
        """Initialize the Samsung device."""

        self._name = name
        self._uuid = uuid
        self._manufacturer = manufacturer
        self._model = model
        self._on_script = on_script
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
            "timeout": None,
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
        if self._on_script:
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
            await self.hass.async_add_job(self.send_key, "KEY_" + digit)
            await asyncio.sleep(KEY_PRESS_TIMEOUT, self.hass.loop)
        await self.hass.async_add_job(self.send_key, "KEY_ENTER")

    async def async_turn_on(self):
        """Turn the media player on."""
        if self._on_script:
            await self.hass.async_add_job(self._on_script.async_run())
        else:
            self.send_key("KEY_POWERON")

    async def async_select_source(self, source):
        """Select input source."""
        if source not in SOURCES:
            LOGGER.error("Unsupported source")
            return

        await self.hass.async_add_job(self.send_key, SOURCES[source])
