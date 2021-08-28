"""Support for DLNA DMR (Device Media Renderer)."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import functools
import logging

import aiohttp
from async_upnp_client import UpnpFactory
from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.profiles.dlna import DeviceState, DmrDevice
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.components.network import async_get_source_ip
from homeassistant.components.network.const import PUBLIC_TARGET_IP
from homeassistant.const import (
    CONF_NAME,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DLNA_DMR_DATA = "dlna_dmr"

DEFAULT_NAME = "DLNA Digital Media Renderer"
DEFAULT_LISTEN_PORT = 8301

CONF_LISTEN_IP = "listen_ip"
CONF_LISTEN_PORT = "listen_port"
CONF_CALLBACK_URL_OVERRIDE = "callback_url_override"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_LISTEN_IP): cv.string,
        vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CALLBACK_URL_OVERRIDE): cv.url,
    }
)


def catch_request_errors():
    """Catch asyncio.TimeoutError, aiohttp.ClientError errors."""

    def call_wrapper(func):
        """Call wrapper for decorator."""

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            """Catch asyncio.TimeoutError, aiohttp.ClientError errors."""
            try:
                return await func(self, *args, **kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientError):
                _LOGGER.error("Error during call %s", func.__name__)

        return wrapper

    return call_wrapper


async def async_start_event_handler(
    hass: HomeAssistant,
    server_host: str,
    server_port: int,
    requester,
    callback_url_override: str | None = None,
):
    """Register notify view."""
    hass_data = hass.data[DLNA_DMR_DATA]
    if "event_handler" in hass_data:
        return hass_data["event_handler"]

    # start event handler
    server = AiohttpNotifyServer(
        requester,
        listen_port=server_port,
        listen_host=server_host,
        callback_url=callback_url_override,
    )
    await server.start_server()
    _LOGGER.info("UPNP/DLNA event handler listening, url: %s", server.callback_url)
    hass_data["notify_server"] = server
    hass_data["event_handler"] = server.event_handler

    # register for graceful shutdown
    async def async_stop_server(event):
        """Stop server."""
        _LOGGER.debug("Stopping UPNP/DLNA event handler")
        await server.stop_server()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_server)

    return hass_data["event_handler"]


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up DLNA DMR platform."""
    if config.get(CONF_URL) is not None:
        url = config[CONF_URL]
        name = config.get(CONF_NAME)
    elif discovery_info is not None:
        url = discovery_info["ssdp_description"]
        name = discovery_info.get("name")

    if DLNA_DMR_DATA not in hass.data:
        hass.data[DLNA_DMR_DATA] = {}

    if "lock" not in hass.data[DLNA_DMR_DATA]:
        hass.data[DLNA_DMR_DATA]["lock"] = asyncio.Lock()

    # build upnp/aiohttp requester
    session = async_get_clientsession(hass)
    requester = AiohttpSessionRequester(session, True)

    # ensure event handler has been started
    async with hass.data[DLNA_DMR_DATA]["lock"]:
        server_host = config.get(CONF_LISTEN_IP)
        if server_host is None:
            server_host = await async_get_source_ip(hass, PUBLIC_TARGET_IP)
        server_port = config.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)
        callback_url_override = config.get(CONF_CALLBACK_URL_OVERRIDE)
        event_handler = await async_start_event_handler(
            hass, server_host, server_port, requester, callback_url_override
        )

    # create upnp device
    factory = UpnpFactory(requester, non_strict=True)
    try:
        upnp_device = await factory.async_create_device(url)
    except (asyncio.TimeoutError, aiohttp.ClientError) as err:
        raise PlatformNotReady() from err

    # wrap with DmrDevice
    dlna_device = DmrDevice(upnp_device, event_handler)

    # create our own device
    device = DlnaDmrDevice(dlna_device, name)
    _LOGGER.debug("Adding device: %s", device)
    async_add_entities([device], True)


class DlnaDmrDevice(MediaPlayerEntity):
    """Representation of a DLNA DMR device."""

    def __init__(self, dmr_device, name=None):
        """Initialize DLNA DMR device."""
        self._device = dmr_device
        self._name = name

        self._available = False
        self._subscription_renew_time = None

    async def async_added_to_hass(self):
        """Handle addition."""
        self._device.on_event = self._on_event

        # Register unsubscribe on stop
        bus = self.hass.bus
        bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_on_hass_stop)

    @property
    def available(self):
        """Device is available."""
        return self._available

    async def _async_on_hass_stop(self, event):
        """Event handler on Home Assistant stop."""
        async with self.hass.data[DLNA_DMR_DATA]["lock"]:
            await self._device.async_unsubscribe_services()

    async def async_update(self):
        """Retrieve the latest data."""
        was_available = self._available

        try:
            await self._device.async_update()
            self._available = True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            self._available = False
            _LOGGER.debug("Device unavailable")
            return

        # do we need to (re-)subscribe?
        now = dt_util.utcnow()
        should_renew = (
            self._subscription_renew_time and now >= self._subscription_renew_time
        )
        if should_renew or not was_available and self._available:
            try:
                timeout = await self._device.async_subscribe_services()
                self._subscription_renew_time = dt_util.utcnow() + timeout / 2
            except (asyncio.TimeoutError, aiohttp.ClientError):
                self._available = False
                _LOGGER.debug("Could not (re)subscribe")

    def _on_event(self, service, state_variables):
        """State variable(s) changed, let home-assistant know."""
        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported_features = 0

        if self._device.has_volume_level:
            supported_features |= SUPPORT_VOLUME_SET
        if self._device.has_volume_mute:
            supported_features |= SUPPORT_VOLUME_MUTE
        if self._device.has_play:
            supported_features |= SUPPORT_PLAY
        if self._device.has_pause:
            supported_features |= SUPPORT_PAUSE
        if self._device.has_stop:
            supported_features |= SUPPORT_STOP
        if self._device.has_previous:
            supported_features |= SUPPORT_PREVIOUS_TRACK
        if self._device.has_next:
            supported_features |= SUPPORT_NEXT_TRACK
        if self._device.has_play_media:
            supported_features |= SUPPORT_PLAY_MEDIA
        if self._device.has_seek_rel_time:
            supported_features |= SUPPORT_SEEK

        return supported_features

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._device.has_volume_level:
            return self._device.volume_level
        return 0

    @catch_request_errors()
    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._device.async_set_volume_level(volume)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._device.is_volume_muted

    @catch_request_errors()
    async def async_mute_volume(self, mute):
        """Mute the volume."""
        desired_mute = bool(mute)
        await self._device.async_mute_volume(desired_mute)

    @catch_request_errors()
    async def async_media_pause(self):
        """Send pause command."""
        if not self._device.can_pause:
            _LOGGER.debug("Cannot do Pause")
            return

        await self._device.async_pause()

    @catch_request_errors()
    async def async_media_play(self):
        """Send play command."""
        if not self._device.can_play:
            _LOGGER.debug("Cannot do Play")
            return

        await self._device.async_play()

    @catch_request_errors()
    async def async_media_stop(self):
        """Send stop command."""
        if not self._device.can_stop:
            _LOGGER.debug("Cannot do Stop")
            return

        await self._device.async_stop()

    @catch_request_errors()
    async def async_media_seek(self, position):
        """Send seek command."""
        if not self._device.can_seek_rel_time:
            _LOGGER.debug("Cannot do Seek/rel_time")
            return

        time = timedelta(seconds=position)
        await self._device.async_seek_rel_time(time)

    @catch_request_errors()
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Playing media: %s, %s, %s", media_type, media_id, kwargs)
        title = "Home Assistant"

        # Stop current playing media
        if self._device.can_stop:
            await self.async_media_stop()

        # Queue media
        await self._device.async_set_transport_uri(media_id, title)
        await self._device.async_wait_for_can_play()

        # If already playing, no need to call Play
        if self._device.state == DeviceState.PLAYING:
            return

        # Play it
        await self.async_media_play()

    @catch_request_errors()
    async def async_media_previous_track(self):
        """Send previous track command."""
        if not self._device.can_previous:
            _LOGGER.debug("Cannot do Previous")
            return

        await self._device.async_previous()

    @catch_request_errors()
    async def async_media_next_track(self):
        """Send next track command."""
        if not self._device.can_next:
            _LOGGER.debug("Cannot do Next")
            return

        await self._device.async_next()

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._device.media_title

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._device.media_image_url

    @property
    def state(self):
        """State of the player."""
        if not self._available:
            return STATE_OFF

        if self._device.state is None:
            return STATE_ON
        if self._device.state == DeviceState.PLAYING:
            return STATE_PLAYING
        if self._device.state == DeviceState.PAUSED:
            return STATE_PAUSED

        return STATE_IDLE

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._device.media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._device.media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._device.media_position_updated_at

    @property
    def name(self) -> str:
        """Return the name of the device."""
        if self._name:
            return self._name
        return self._device.name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self._device.udn
