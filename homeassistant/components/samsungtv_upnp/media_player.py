"""Support for Samsung TV via UPNP."""
import asyncio
from datetime import datetime
import functools
import logging
from typing import Optional

import aiohttp
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL, SUPPORT_SELECT_SOURCE)
from homeassistant.const import (
    CONF_NAME, CONF_URL, EVENT_HOMEASSISTANT_STOP, STATE_OFF,
    STATE_IDLE, STATE_PLAYING)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.helpers.config_validation as cv
from homeassistant.util import get_local_ip

_LOGGER = logging.getLogger(__name__)

SAMSUNGTV_UPNP_DATA = 'samsungtv_upnp'
SAMSUNGTV_UPNP_SUPPORT = SUPPORT_SELECT_SOURCE

SAMSUNGTV_UPNP_DEVICE_TYPES = [
        'urn:samsung.com:device:MainTVServer2:1',
]
SAMSUNGTV_UPNP_SERVICE_TYPES = {
        'MTVA': {
            'urn:samsung.com:service:MainTVAgent2:1',
        },
}

DEFAULT_NAME = 'Samsung TV'
DEFAULT_LISTEN_PORT = 7676

CONF_LISTEN_IP = 'listen_ip'
CONF_LISTEN_PORT = 'listen_port'
CONF_CALLBACK_URL_OVERRIDE = 'callback_url_override'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_LISTEN_IP): cv.string,
    vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CALLBACK_URL_OVERRIDE): cv.url,
})


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


async def async_start_event_handler(
        hass: HomeAssistantType,
        server_host: str,
        server_port: int,
        requester,
        callback_url_override: Optional[str] = None):
    """Register notify view."""
    hass_data = hass.data[SAMSUNGTV_UPNP_DATA]
    if 'event_handler' in hass_data:
        return hass_data['event_handler']

    # start event handler
    from async_upnp_client.aiohttp import AiohttpNotifyServer
    server = AiohttpNotifyServer(
        requester,
        listen_port=server_port,
        listen_host=server_host,
        loop=hass.loop,
        callback_url=callback_url_override)
    await server.start_server()
    _LOGGER.info(
        'Samsung TV UPNP event handler listening, url: %s', server.callback_url)
    hass_data['notify_server'] = server
    hass_data['event_handler'] = server.event_handler

    # register for graceful shutdown
    async def async_stop_server(event):
        """Stop server."""
        _LOGGER.debug('Stopping Samsung TV UPNP event handler')
        await server.stop_server()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_server)

    return hass_data['event_handler']


async def async_setup_platform(
        hass: HomeAssistantType,
        config,
        async_add_entities,
        discovery_info=None):
    """Set up Samsung TV UPNP platform."""
    if config.get(CONF_URL) is not None:
        url = config[CONF_URL]
        name = config.get(CONF_NAME)
    elif discovery_info is not None:
        url = discovery_info['ssdp_description']
        name = discovery_info.get('name')

    if SAMSUNGTV_UPNP_DATA not in hass.data:
        hass.data[SAMSUNGTV_UPNP_DATA] = {}

    if 'lock' not in hass.data[SAMSUNGTV_UPNP_DATA]:
        hass.data[SAMSUNGTV_UPNP_DATA]['lock'] = asyncio.Lock()

    # build upnp/aiohttp requester
    from async_upnp_client.aiohttp import AiohttpSessionRequester
    session = async_get_clientsession(hass)
    requester = AiohttpSessionRequester(session, True)

    # ensure event handler has been started
    with await hass.data[SAMSUNGTV_UPNP_DATA]['lock']:
        server_host = config.get(CONF_LISTEN_IP)
        if server_host is None:
            server_host = get_local_ip()
        server_port = config.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)
        callback_url_override = config.get(CONF_CALLBACK_URL_OVERRIDE)
        event_handler = await async_start_event_handler(
            hass, server_host, server_port, requester, callback_url_override)

    # create upnp device
    from async_upnp_client import (UpnpFactory, UpnpError)
    factory = UpnpFactory(requester, disable_state_variable_validation=True)
    try:
        upnp_device = await factory.async_create_device(url)
    except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
        raise PlatformNotReady()

    # wrap with UpnpProfileDevice
    from async_upnp_client.profiles.profile import UpnpProfileDevice
    upnp_device = UpnpProfileDevice(upnp_device, event_handler)
    upnp_device.DEVICE_TYPES = SAMSUNGTV_UPNP_DEVICE_TYPES
    upnp_device._SERVICE_TYPES = SAMSUNGTV_UPNP_SERVICE_TYPES

    # create our own device
    device = SamsungTvUpnpDevice(upnp_device, name)
    _LOGGER.debug("Adding device: %s", device)
    async_add_entities([device], True)


class SamsungTvUpnpDevice(MediaPlayerDevice):
    """Representation of a Samsung TV UPNP device."""

    def __init__(self, upnp_device, name=None):
        """Initializer."""
        self._device = upnp_device
        self._name = name

        self._available = False
        self._source = None
        self._source_list = None
        self._media_channel = None
        self._media_title = None
        self._subscription_renew_time = None

    async def async_added_to_hass(self):
        """Handle addition."""
        bus = self.hass.bus
        bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_on_hass_stop)

    async def _async_on_hass_stop(self, event):
        """Event handler on HASS stop."""
        with await self.hass.data[SAMSUNGTV_UPNP_DATA]['lock']:
            await self._device.async_unsubscribe_services()

    async def async_update(self):
        """Retrieve the latest data."""
        was_available = self._available
        try:
            await self._device.device.async_ping()
            self._available = True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            self._available = False
            _LOGGER.debug("Device unavailable")
            return

        await self._get_source()
        await self._get_media_info()

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

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SAMSUNGTV_UPNP_SUPPORT

    @property
    def available(self):
        """Device is available."""
        return self._available

    @property
    def state(self):
        """State of the player."""
        if not self._available:
            return STATE_OFF
        elif self._source == 'TV':
            return STATE_PLAYING
        return STATE_IDLE

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._source_list)

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def media_channel(self):
        """Channel currently playing"""
        return self._media_channel

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL if self._media_channel else None

    async def async_select_source(self, source):
        """Select input source."""
        if source not in self._source_list:
            _LOGGER.debug('Unsupported source')
            return
        id = self._source_list[source]

        action = self._device._action('MTVA', 'SetMainTVSource')
        if not action:
            _LOGGER.debug('Missing action MTVA/SetMainTVSource')
            return

        try:
            result = await action.async_call(Source=source, ID=id, UiID=0)
        except:
            result = None
        if not result or result.get('Result') != 'OK':
            _LOGGER.debug('unable to select source')
            return

        self._source = source

    async def _get_source(self):
        from collections import OrderedDict
        from xml.dom.minidom import parseString

        self._source = None
        self._source_list = None

        action = self._device._action('MTVA', 'GetSourceList')
        if not action:
            _LOGGER.debug('Missing action MTVA/GetSourceList')
            return

        try:
            result = await action.async_call()
        except:
            result = None
        if not result or result.get('Result') != 'OK':
            _LOGGER.debug('unable to get sources')
            return

        dom = parseString(result.get('SourceList'))
        self._source = dom.getElementsByTagName('CurrentSourceType')[0] \
                          .firstChild.nodeValue
        self._source_list = OrderedDict()
        for node in dom.getElementsByTagName('Source'):
            if node.getElementsByTagName('Connected')[0].firstChild \
                                                        .nodeValue == 'Yes':
                name = node.getElementsByTagName('SourceType')[0] .firstChild.nodeValue
                id = int(node.getElementsByTagName('ID')[0] .firstChild.nodeValue)
                self._source_list[name] = id

    async def _get_media_info(self):
        self._media_channel = None
        self._media_title = None

        action = self._device._action('MTVA', 'GetCurrentContentRecognition')
        if not action:
            _LOGGER.debug('Missing action MTVA/GetCurrentContentRecognition')
            return

        try:
            result = await action.async_call()
        except:
            result = None
        if not result or result.get('Result') != 'OK':
            _LOGGER.debug('unable to get media title')
            return

        self._media_channel = result.get('ChannelName')
        self._media_title = result.get('ProgramTitle')
