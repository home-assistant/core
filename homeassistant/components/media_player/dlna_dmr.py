# -*- coding: utf-8 -*-
"""
Support for DLNA DMR (Device Media Renderer).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.dlna_dmr/
"""

import asyncio
import logging
import urllib.parse
from datetime import datetime

import aiohttp
import async_timeout
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


REQUIREMENTS = [
    'async-upnp-client==0.12.0',
]

DEPENDENCIES = ['http']

DEFAULT_NAME = 'DLNA Digital Media Renderer'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

SUPPORT_DLNA_DMR = \
    SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
    SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_PAUSE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA

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

UPNP_DEVICE_MEDIA_RENDERER = 'urn:schemas-upnp-org:device:MediaRenderer:1'

_LOGGER = logging.getLogger(__name__)


def start_notify_view(hass, requester):
    """Register notify view."""
    hass_data = hass.data[__name__]
    name = 'notify_view'
    if name in hass_data:
        return

    view = UpnpNotifyView(hass)
    hass.http.register_view(view)
    hass_data[name] = view

    from async_upnp_client import UpnpEventHandler
    view.event_handler = UpnpEventHandler(view.callback_url, requester)


async def async_setup_platform(hass: HomeAssistant,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up DLNA DMR platform."""
    # ensure this is a DLNA DMR device, if found via discovery
    if discovery_info and \
       'upnp_device_type' in discovery_info and \
       discovery_info['upnp_device_type'] != UPNP_DEVICE_MEDIA_RENDERER:
        _LOGGER.debug('Device is not a MediaRenderer: %s, device_type: %s',
                      discovery_info.get('ssdp_description'),
                      discovery_info['upnp_device_type'])
        return

    if config.get(CONF_URL) is not None:
        url = config.get(CONF_URL)
        name = config.get(CONF_NAME)
    elif discovery_info is not None:
        url = discovery_info['ssdp_description']
        name = discovery_info['name']

    if __name__ not in hass.data:
        hass.data[__name__] = {}

    requester = build_requester(hass)

    # ensure view has been started
    hass.async_run_job(start_notify_view, hass, requester)
    while 'notify_view' not in hass.data[__name__]:
        asyncio.sleep(0.1)
    notify_view = hass.data[__name__]['notify_view']

    # create device
    from async_upnp_client import UpnpFactory
    from async_upnp_client.dlna import DmrDevice
    factory = UpnpFactory(requester, disable_state_variable_validation=True)
    try:
        upnp_device = await factory.async_create_device(url)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    dlna_device = DmrDevice(upnp_device, notify_view.event_handler)
    device = DlnaDmrDevice(hass, dlna_device, name)

    _LOGGER.debug("Adding device: %s", device)
    async_add_devices([device])


class UpnpNotifyView(HomeAssistantView):
    """Callback view for UPnP NOTIFY messages."""

    url = '/api/dlna_dmr.notify'
    name = 'api:dlna_dmr:notify'
    requires_auth = False

    def __init__(self, hass):
        """Initializer."""
        self.hass = hass
        self.event_handler = None
        self._registered_services = {}
        self._backlog = {}

    def register(self, router):
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
        base_url = self.hass.config.api.base_url
        return urllib.parse.urljoin(base_url, self.url)


def build_requester(hass):
    """Build a derived instance of UpnpRequester, specific for hass."""
    from async_upnp_client import UpnpRequester

    class HassUpnpRequester(UpnpRequester):
        """async_upnp_client.UpnpRequester for home-assistant."""

        def __init__(self, hass_):
            """Initializer."""
            self.hass = hass_

        async def async_do_http_request(self,
                                        method,
                                        url,
                                        headers=None,
                                        body=None,
                                        body_type='text'):
            """Do a HTTP request."""
            # work around an unknown hass or aiohttp error
            await asyncio.sleep(0.01)

            session = async_get_clientsession(self.hass)
            with async_timeout.timeout(5, loop=self.hass.loop):
                response = await session.request(method,
                                                 url,
                                                 headers=headers,
                                                 data=body)
                if body_type == 'text':
                    response_body = await response.text()
                elif body_type == 'raw':
                    response_body = await response.read()
                elif body_type == 'ignore':
                    response_body = None

            return response.status, response.headers, response_body

    return HassUpnpRequester(hass)


class DlnaDmrDevice(MediaPlayerDevice):
    """Representation of a DLNA DMR device."""

    def __init__(self, hass: HomeAssistant, dmr_device, name=None):
        """Initializer."""
        self.hass = hass
        self._name = name

        self._device = dmr_device
        self._device.on_event = self._on_event

        self._available = False
        self._on_stop_unsubscriber = None
        self._subscription_renew_time = None

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
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
        await self._device.async_unsubscribe_services()

    async def async_update(self):
        """Retrieve the latest data."""
        was_available = self._available

        try:
            await self._device.async_update()
            self._available = True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            self._available = False
            _LOGGER.debug("Device unavailable 1")
            raise

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
                _LOGGER.debug("Device unavailable 2")
                raise

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

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        try:
            await self._device.async_set_volume_level(volume)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during RC/SetVolume call")

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._device.is_volume_muted

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        desired_mute = bool(mute)
        try:
            await self._device.async_mute_volume(desired_mute)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during RC/SetMute call")

    async def async_media_pause(self):
        """Send pause command."""
        if not self._device.can_pause:
            _LOGGER.debug('Cannot do Pause')
            return

        try:
            await self._device.async_pause()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during AVT/Pause call")

    async def async_media_play(self):
        """Send play command."""
        if not self._device.can_play:
            _LOGGER.debug('Cannot do Play')
            return

        try:
            await self._device.async_play()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during AVT/Play call")

    async def async_media_stop(self):
        """Send stop command."""
        if not self._device.can_stop:
            _LOGGER.debug('Cannot do Stop')
            return

        try:
            await self._device.async_stop()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during AVT/Stop call")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        title = "Home Assistant"
        mime_type = HOME_ASSISTANT_UPNP_MIME_TYPE_MAPPING[media_type]
        upnp_class = HOME_ASSISTANT_UPNP_CLASS_MAPPING[media_type]

        # stop current playing media
        if self._device.can_stop:
            await self.async_media_stop()

        # queue media
        try:
            await self._device.async_set_transport_uri(media_id,
                                                       title,
                                                       mime_type,
                                                       upnp_class)
            await self._device.async_wait_for_can_play()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during SetAVTransportURI or wait call")
            return

        # if already playing, no need to call Play
        from async_upnp_client import dlna
        if self._device.state == dlna.STATE_PLAYING:
            return

        # play it
        await self.async_media_play()

    async def async_media_previous_track(self):
        """Send previous track command."""
        if not self._device.can_previous:
            _LOGGER.debug('Cannot do Previous')
            return

        try:
            await self._device.async_previous()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during Previous call")

    async def async_media_next_track(self):
        """Send next track command."""
        if self._device.can_next:
            _LOGGER.debug('Cannot do Next')
            return

        try:
            await self._device.async_next()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error during Next call")

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
        return "{}.{}".format(__name__, self.udn)

    def __str__(self) -> str:
        """To string."""
        return "<DlnaDmrDevice('{}')>".format(self.udn)

    def __repr__(self) -> str:
        """Repr."""
        return "<DlnaDmrDevice('{}')>".format(self.udn)
