# -*- coding: utf-8 -*-
"""
Support for DLNA DMR (Device Media Renderer).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.dlna_dmr/
"""

import asyncio
import functools
import logging
import socket
import urllib.parse
from datetime import datetime

import aiohttp
import aiohttp.web
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http.view import (
    request_handler_factory, HomeAssistantView)
from homeassistant.components.media_player import (
    SUPPORT_PLAY, SUPPORT_PAUSE, SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    CONF_URL, CONF_NAME,
    STATE_OFF, STATE_ON, STATE_IDLE, STATE_PLAYING, STATE_PAUSED)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession


DLNA_DMR_DATA = 'dlna_dmr'

REQUIREMENTS = [
    'async-upnp-client==0.12.1',
]

DEPENDENCIES = []

DEFAULT_NAME = 'DLNA Digital Media Renderer'
DEFAULT_LISTEN_PORT = 8301

CONF_LISTEN_IP = 'listen_ip'
CONF_LISTEN_PORT = 'listen_port'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_LISTEN_IP): cv.string,
    vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

HOME_ASSISTANT_UPNP_CLASS_MAPPING = {
    'music': 'object.item.audioItem',
    'tvshow': 'object.item.videoItem',
    'video': 'object.item.videoItem',
    'episode': 'object.item.videoItem',
    'channel': 'object.item.videoItem',
    'playlist': 'object.item.playlist',
}
HOME_ASSISTANT_UPNP_MIME_TYPE_MAPPING = {
    'music': 'audio/*',
    'tvshow': 'video/*',
    'video': 'video/*',
    'episode': 'video/*',
    'channel': 'video/*',
    'playlist': 'playlist/*',
}
UPNP_DEVICE_MEDIA_RENDERER = [
    'urn:schemas-upnp-org:device:MediaRenderer:1',
    'urn:schemas-upnp-org:device:MediaRenderer:2',
    'urn:schemas-upnp-org:device:MediaRenderer:3',
]

_LOGGER = logging.getLogger(__name__)

ASYNC_LOCK = asyncio.Lock()


def catch_request_errors():
    """Catch asyncio.TimeoutError, aiohttp.ClientError errors."""
    def call_wrapper(func):
        """Call wrapper for decorator."""
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            """Catch asyncio.TimeoutError, aiohttp.ClientError errors."""
            try:
                return func(self, *args, **kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientError):
                _LOGGER.error("Error during call %s", func.__name__)

        return wrapper

    return call_wrapper


def determine_listen_ip(target_url, config):
    """
    Determine the IP and port to listen on.

    If specified in config, use config.
    Otherwise try to figure it out.
    """
    server_host = config.get(CONF_LISTEN_IP)
    server_port = config.get(CONF_LISTEN_PORT)

    if server_host is None:
        # determine server_host by opening a UDP socket to target,
        # but don't actually send anything
        parsed = urllib.parse.urlparse(target_url)
        target_host = parsed.hostname
        target_port = parsed.port
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect((target_host, target_port))
        server_host = temp_sock.getsockname()[0]
        temp_sock.close()

    return server_host, server_port


async def async_start_notify_view(hass, server_host, server_port, requester):
    """Register notify view."""
    hass_data = hass.data[DLNA_DMR_DATA]
    if 'notify_view' in hass_data:
        return hass_data['notify_view']

    app = aiohttp.web.Application()
    app['hass'] = hass
    handler = None
    server = None
    hass_data['notify_server'] = app

    base_url = 'http://{}:{}/'.format(server_host, server_port)
    view = UpnpNotifyView(base_url)
    hass_data['notify_view'] = view
    view.register(app, app.router)

    from async_upnp_client import UpnpEventHandler
    view.event_handler = UpnpEventHandler(view.callback_url, requester)

    async def async_stop_server(event):
        """Stop server."""
        _LOGGER.debug('Stopping NOTIFY server')
        if server:
            server.close()
            await server.wait_closed()
        await app.shutdown()
        if handler:
            await handler.shutdown(10)
        await app.cleanup()

    async def async_start_server():
        """Start server."""
        _LOGGER.debug('Starting NOTIFY server')
        nonlocal handler
        nonlocal server
        handler = app.make_handler(loop=hass.loop)
        try:
            server = await hass.loop.create_server(
                handler, server_host, server_port)
        except OSError as error:
            _LOGGER.error("Failed to create HTTP server at port %d: %s",
                          server_port, error)

    await async_start_server()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_server)

    _LOGGER.info('UPNP/DLNA notify server listening on: %s', base_url)
    return view


async def async_setup_platform(hass: HomeAssistant,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up DLNA DMR platform."""
    # ensure this is a DLNA DMR device, if found via discovery
    if discovery_info and \
       'upnp_device_type' in discovery_info and \
       discovery_info['upnp_device_type'] not in UPNP_DEVICE_MEDIA_RENDERER:
        _LOGGER.debug('Device is not a MediaRenderer: %s, device_type: %s',
                      discovery_info.get('ssdp_description'),
                      discovery_info['upnp_device_type'])
        return

    if config.get(CONF_URL) is not None:
        url = config[CONF_URL]
        name = config.get(CONF_NAME)
    elif discovery_info is not None:
        url = discovery_info['ssdp_description']
        name = discovery_info['name']

    if DLNA_DMR_DATA not in hass.data:
        hass.data[DLNA_DMR_DATA] = {}

    # build requester
    from async_upnp_client.aiohttp import AiohttpSessionRequester
    session = async_get_clientsession(hass)
    requester = AiohttpSessionRequester(session, True)

    # ensure view has been started
    with (await ASYNC_LOCK):
        # discovered components don't get default values in config
        config[CONF_LISTEN_PORT] = config.get(CONF_LISTEN_PORT,
                                              DEFAULT_LISTEN_PORT)
        server_host, server_port = determine_listen_ip(url, config)
        notify_view = await async_start_notify_view(hass,
                                                    server_host,
                                                    server_port,
                                                    requester)

    # create device
    from async_upnp_client import UpnpFactory
    from async_upnp_client.dlna import DmrDevice
    factory = UpnpFactory(requester, disable_state_variable_validation=True)
    try:
        upnp_device = await factory.async_create_device(url)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    dlna_device = DmrDevice(upnp_device, notify_view.event_handler)
    device = DlnaDmrDevice(dlna_device, name)

    _LOGGER.debug("Adding device: %s", device)
    async_add_devices([device], True)


class UpnpNotifyView(HomeAssistantView):
    """Callback view for UPnP NOTIFY messages."""

    url = '/api/dlna_dmr.notify'
    name = 'dlna_dmr:api:notify'
    requires_auth = False

    def __init__(self, base_url):
        """Initializer."""
        self.base_url = base_url
        self.event_handler = None
        self._registered_services = {}
        self._backlog = {}

    def register(self, app, router):
        """Register the view with a router."""
        handler = request_handler_factory(self, self.async_notify)
        router.add_route('notify', UpnpNotifyView.url, handler)

    async def async_notify(self, request):
        """Callback method for NOTIFY requests."""
        headers = request.headers
        body = await request.text()
        status = await self.event_handler.handle_notify(headers, body)
        return aiohttp.web.Response(status=status)

    @property
    def callback_url(self):
        """Full URL to be called by device/service."""
        return urllib.parse.urljoin(self.base_url, self.url)


class DlnaDmrDevice(MediaPlayerDevice):
    """Representation of a DLNA DMR device."""

    def __init__(self, dmr_device, name=None):
        """Initializer."""
        self._device = dmr_device
        self._name = name

        self._available = False
        self._subscription_renew_time = None

    async def async_added_to_hass(self):
        """Callback when added."""
        self._device.on_event = self._on_event

        # register unsubscribe on stop
        bus = self.hass.bus
        bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                              self._async_on_hass_stop)

    @property
    def udn(self):
        """Get UDN of DLNA DMR device."""
        return self._device.udn

    @property
    def available(self):
        """Device is available."""
        return self._available

    async def _async_on_hass_stop(self, event):
        """Event handler on HASS stop."""
        with (await ASYNC_LOCK):
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
        now = datetime.now()
        should_renew = self._subscription_renew_time and \
            now >= self._subscription_renew_time
        if should_renew or \
           not was_available and self._available:
            try:
                timeout = await self._device.async_subscribe_services()
                self._subscription_renew_time = datetime.now() + timeout / 2
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

        return supported_features

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._device.volume_level

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
            _LOGGER.debug('Cannot do Pause')
            return

        await self._device.async_pause()

    @catch_request_errors()
    async def async_media_play(self):
        """Send play command."""
        if not self._device.can_play:
            _LOGGER.debug('Cannot do Play')
            return

        await self._device.async_play()

    @catch_request_errors()
    async def async_media_stop(self):
        """Send stop command."""
        if not self._device.can_stop:
            _LOGGER.debug('Cannot do Stop')
            return

        await self._device.async_stop()

    @catch_request_errors()
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        title = "Home Assistant"
        mime_type = HOME_ASSISTANT_UPNP_MIME_TYPE_MAPPING[media_type]
        upnp_class = HOME_ASSISTANT_UPNP_CLASS_MAPPING[media_type]

        # stop current playing media
        if self._device.can_stop:
            await self.async_media_stop()

        # queue media
        await self._device.async_set_transport_uri(media_id,
                                                   title,
                                                   mime_type,
                                                   upnp_class)
        await self._device.async_wait_for_can_play()

        # if already playing, no need to call Play
        from async_upnp_client import dlna
        if self._device.state == dlna.STATE_PLAYING:
            return

        # play it
        await self.async_media_play()

    @catch_request_errors()
    async def async_media_previous_track(self):
        """Send previous track command."""
        if not self._device.can_previous:
            _LOGGER.debug('Cannot do Previous')
            return

        await self._device.async_previous()

    @catch_request_errors()
    async def async_media_next_track(self):
        """Send next track command."""
        if not self._device.can_next:
            _LOGGER.debug('Cannot do Next')
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

        from async_upnp_client import dlna
        if self._device.state is None:
            return STATE_ON
        elif self._device.state == dlna.STATE_PLAYING:
            return STATE_PLAYING
        elif self._device.state == dlna.STATE_PAUSED:
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
        return self.udn
