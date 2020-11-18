"""Support for FFmpeg."""
import re

from haffmpeg.tools import FFVersion
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONTENT_TYPE_MULTIPART,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

DOMAIN = "ffmpeg"

SERVICE_START = "start"
SERVICE_STOP = "stop"
SERVICE_RESTART = "restart"

SIGNAL_FFMPEG_START = "ffmpeg.start"
SIGNAL_FFMPEG_STOP = "ffmpeg.stop"
SIGNAL_FFMPEG_RESTART = "ffmpeg.restart"

DATA_FFMPEG = "ffmpeg"

CONF_INITIAL_STATE = "initial_state"
CONF_INPUT = "input"
CONF_FFMPEG_BIN = "ffmpeg_bin"
CONF_EXTRA_ARGUMENTS = "extra_arguments"
CONF_OUTPUT = "output"

DEFAULT_BINARY = "ffmpeg"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_FFMPEG_BIN, default=DEFAULT_BINARY): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_FFMPEG_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})


async def async_setup(hass, config):
    """Set up the FFmpeg component."""
    conf = config.get(DOMAIN, {})

    manager = FFmpegManager(hass, conf.get(CONF_FFMPEG_BIN, DEFAULT_BINARY))

    await manager.async_get_version()

    # Register service
    async def async_service_handle(service):
        """Handle service ffmpeg process."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if service.service == SERVICE_START:
            async_dispatcher_send(hass, SIGNAL_FFMPEG_START, entity_ids)
        elif service.service == SERVICE_STOP:
            async_dispatcher_send(hass, SIGNAL_FFMPEG_STOP, entity_ids)
        else:
            async_dispatcher_send(hass, SIGNAL_FFMPEG_RESTART, entity_ids)

    hass.services.async_register(
        DOMAIN, SERVICE_START, async_service_handle, schema=SERVICE_FFMPEG_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_STOP, async_service_handle, schema=SERVICE_FFMPEG_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, async_service_handle, schema=SERVICE_FFMPEG_SCHEMA
    )

    hass.data[DATA_FFMPEG] = manager
    return True


class FFmpegManager:
    """Helper for ha-ffmpeg."""

    def __init__(self, hass, ffmpeg_bin):
        """Initialize helper."""
        self.hass = hass
        self._cache = {}
        self._bin = ffmpeg_bin
        self._version = None
        self._major_version = None

    @property
    def binary(self):
        """Return ffmpeg binary from config."""
        return self._bin

    async def async_get_version(self):
        """Return ffmpeg version."""

        ffversion = FFVersion(self._bin, self.hass.loop)
        self._version = await ffversion.get_version()

        self._major_version = None
        if self._version is not None:
            result = re.search(r"(\d+)\.", self._version)
            if result is not None:
                self._major_version = int(result.group(1))

        return self._version, self._major_version

    @property
    def ffmpeg_stream_content_type(self):
        """Return HTTP content type for ffmpeg stream."""
        if self._major_version is not None and self._major_version > 3:
            return CONTENT_TYPE_MULTIPART.format("ffmpeg")

        return CONTENT_TYPE_MULTIPART.format("ffserver")


class FFmpegBase(Entity):
    """Interface object for FFmpeg."""

    def __init__(self, initial_state=True):
        """Initialize ffmpeg base object."""
        self.ffmpeg = None
        self.initial_state = initial_state

    async def async_added_to_hass(self):
        """Register dispatcher & events.

        This method is a coroutine.
        """
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_FFMPEG_START, self._async_start_ffmpeg
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_FFMPEG_STOP, self._async_stop_ffmpeg
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_FFMPEG_RESTART, self._async_restart_ffmpeg
            )
        )

        # register start/stop
        self._async_register_events()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.ffmpeg.is_running

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    async def _async_start_ffmpeg(self, entity_ids):
        """Start a FFmpeg process.

        This method is a coroutine.
        """
        raise NotImplementedError()

    async def _async_stop_ffmpeg(self, entity_ids):
        """Stop a FFmpeg process.

        This method is a coroutine.
        """
        if entity_ids is None or self.entity_id in entity_ids:
            await self.ffmpeg.close()

    async def _async_restart_ffmpeg(self, entity_ids):
        """Stop a FFmpeg process.

        This method is a coroutine.
        """
        if entity_ids is None or self.entity_id in entity_ids:
            await self._async_stop_ffmpeg(None)
            await self._async_start_ffmpeg(None)

    @callback
    def _async_register_events(self):
        """Register a FFmpeg process/device."""

        async def async_shutdown_handle(event):
            """Stop FFmpeg process."""
            await self._async_stop_ffmpeg(None)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown_handle)

        # start on startup
        if not self.initial_state:
            return

        async def async_start_handle(event):
            """Start FFmpeg process."""
            await self._async_start_ffmpeg(None)
            self.async_write_ha_state()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_start_handle)
