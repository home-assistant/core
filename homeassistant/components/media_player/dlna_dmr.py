# -*- coding: utf-8 -*-
"""
Support for DLNA DMR (Device Media Renderer).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.dlna_dmr/
"""

import asyncio
import functools
import logging
import re
import urllib.parse
import time
from datetime import timedelta

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
from homeassistant.helpers.aiohttp_client import async_get_clientsession


REQUIREMENTS = [
    'async-upnp-client==0.10.1',
    'python-didl-lite==1.0.1',
]

DEPENDENCIES = ['http']

DEFAULT_NAME = 'DLNA Digital Media Renderer'

CONF_UDN = 'udn'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_UDN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

SUPPORT_DLNA_DMR = \
    SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
    SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_PAUSE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA

SERVICE_TYPES = {
    'RC': 'urn:schemas-upnp-org:service:RenderingControl:1',
    'AVT': 'urn:schemas-upnp-org:service:AVTransport:1',
}

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


def requires_action(service_type, action_name, value_not_connected=None):
    """
    Ensure service/action is available.

    If not available, then raise NotImplemented.
    """
    def call_wrapper(func):
        """Call wrapper for decorator."""
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            """
            Require device is connected and has service/action.

            If device is not connected, value_not_connected is returned.
            """
            # pylint: disable=protected-access

            if not self._is_connected:
                return value_not_connected

            service = self._service(service_type)
            if not service:
                _LOGGER.error('requires_state_variable(): '
                              '%s.%s: no service: %s',
                              self, func.__name__, service_type)
                raise NotImplementedError()

            action = service.action(action_name)
            if not action:
                _LOGGER.error('requires_action(): %s.%s: no action: %s.%s',
                              self, func.__name__, service_type, action_name)
                raise NotImplementedError()
            return func(self, action, *args, **kwargs)

        return wrapper

    return call_wrapper


def requires_state_variable(service_type,
                            state_variable_name,
                            value_not_connected=None):
    """
    Ensure service/state_variable is available.

    If not available, then raise NotImplemented.
    """
    def call_wrapper(func):
        """Call wrapper for decorator."""
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            """
            Require device is connected and has service/state_variable.

            If device is not connected, value_not_connected is returned.
            """
            # pylint: disable=protected-access
            if not self._is_connected:
                return value_not_connected

            service = self._service(service_type)
            if not service:
                _LOGGER.error('requires_state_variable(): '
                              '%s.%s: no service: %s',
                              self,
                              func.__name__, service_type)
                raise NotImplementedError()

            state_var = service.state_variable(state_variable_name)
            if not state_var:
                _LOGGER.error('requires_state_variable(): '
                              '%s.%s: no state_variable: %s.%s',
                              self,
                              func.__name__,
                              service_type,
                              state_variable_name)
                raise NotImplementedError()
            return func(self, state_var, *args, **kwargs)
        return wrapper
    return call_wrapper


def start_notify_view(hass):
    """Register notify view."""
    hass_data = hass.data[__name__]
    name = 'notify_view'
    if name in hass_data:
        return

    view = UpnpNotifyView(hass)
    hass.http.register_view(view)
    hass_data[name] = view


def setup_platform(hass: HomeAssistant, config, add_devices, discovery_info=None):
    """Set up DLNA DMR platform."""
    if discovery_info and \
       'upnp_device_type' in discovery_info and \
       discovery_info['upnp_device_type'] != UPNP_DEVICE_MEDIA_RENDERER:
        _LOGGER.debug('Device is not a MediaRenderer: %s',
                      discovery_info.get('ssdp_description'))
        return

    if config.get(CONF_URL) is not None:
        url = config.get(CONF_URL)
        name = config.get(CONF_NAME)
        udn = config.get(CONF_UDN)
    elif discovery_info is not None:
        url = discovery_info['ssdp_description']
        name = discovery_info['name']
        udn = discovery_info['udn']

    # set up our Views, if not already done so
    if __name__ not in hass.data:
        hass.data[__name__] = {}

    # ensure view has been started
    hass.async_run_job(start_notify_view, hass)
    while 'notify_view' not in hass.data[__name__]:
        time.sleep(0.1)
    notify_view = hass.data[__name__]['notify_view']

    # create device
    from async_upnp_client import UpnpFactory
    requester = HassUpnpRequester(hass)
    factory = UpnpFactory(requester, ignore_state_variable_value_range=True)
    device = DlnaDmrDevice(hass, url, udn, name, factory, notify_view)

    _LOGGER.debug("Adding device: %s", device)
    add_devices([device])


async def fetch_headers(hass, url, headers):
    """Fetch headers from URL, first by trying HEAD, then by trying a GET."""
    # try a HEAD request to the source
    src_response = None
    try:
        session = async_get_clientsession(hass)
        src_response = await session.head(url, headers=headers)
        await src_response.release()
    except aiohttp.ClientError:
        pass

    if src_response and 200 <= src_response.status < 300:
        return src_response.headers

    # try a GET request to the source, but ignore all the data
    session = async_get_clientsession(hass)
    src_response = await session.get(url, headers=headers)
    await src_response.release()

    return src_response.headers


class UpnpNotifyView(HomeAssistantView):
    """Callback view for UPnP NOTIFY messages."""

    url = '/api/dlna_dmr.notify'
    name = 'api:dlna_dmr:notify'
    requires_auth = False

    def __init__(self, hass):
        """Initializer."""
        self.hass = hass
        self._registered_services = {}
        self._backlog = {}

    def register(self, router):
        """Register the view with a router."""
        handler = request_handler_factory(self, self.async_notify)
        router.add_route('notify', UpnpNotifyView.url, handler)

    async def async_notify(self, request):
        """Callback method for NOTIFY requests."""
        if 'SID' not in request.headers:
            return aiohttp.web.Response(status=412)

        headers = request.headers
        sid = headers['SID']
        body = await request.text()

        # find UpnpService by SID
        if sid not in self._registered_services:
            _LOGGER.debug('Storing NOTIFY in backlog for SID: %s', sid)
            self._backlog[sid] = {'headers': headers, 'body': body}
            return aiohttp.web.Response(status=202)

        service = self._registered_services[sid]
        status = service.on_notify(headers, body)
        return aiohttp.web.Response(status=status)

    @property
    def callback_url(self):
        """Full URL to be called by device/service."""
        base_url = self.hass.config.api.base_url
        return urllib.parse.urljoin(base_url, self.url)

    def register_service(self, sid, service):
        """Register a UpnpService under SID."""
        if sid in self._registered_services:
            raise RuntimeError('SID {} already registered.'.format(sid))

        self._registered_services[sid] = service

        if sid in self._backlog:
            item = self._backlog[sid]
            _LOGGER.debug('Re-playing backlogged NOTIFY for SID: %s', sid)
            service.on_notify(item['headers'], item['body'])
            del self._backlog[sid]

    def unregister_service(self, sid):
        """Unregister service by SID."""
        if sid in self._registered_services:
            del self._registered_services[sid]


class HassUpnpRequester(object):
    """async_upnp_client.UpnpRequester for home-assistant."""

    def __init__(self, hass):
        """Initializer."""
        self.hass = hass

    async def async_http_request(self, method, url, headers=None, body=None):
        """Do a HTTP request."""
        session = async_get_clientsession(self.hass)
        with async_timeout.timeout(5, loop=self.hass.loop):
            response = await session.request(method,
                                             url,
                                             headers=headers,
                                             data=body)
            response_body = await response.text()
            await response.release()
        await asyncio.sleep(0.25)

        return response.status, response.headers, response_body


class DlnaDmrDevice(MediaPlayerDevice):
    """Representation of a DLNA DMR device."""

    def __init__(self, hass, url, udn, name, factory, notify_view):
        """Initializer."""
        self.hass = hass
        self._url = url
        self._udn = udn
        self._name = name
        self._factory = factory
        self._notify_view = notify_view

        self._device = None
        self._is_connected = False

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             self._async_on_hass_stop)

    @property
    def available(self):
        """Device is available."""
        return self._is_connected

    async def _async_on_hass_stop(self, event):
        """Event handler on HASS stop."""
        await self.async_unsubscribe_all()

    def _service(self, service_type):
        """Get UpnpService by service_type or alias."""
        if not self._device:
            return None

        service_type = SERVICE_TYPES.get(service_type, service_type)
        return self._device.service(service_type)

    async def async_unsubscribe_all(self):
        """
        Disconnect from device.

        This removes all UpnpServices.
        """
        if not self._device:
            return

        for service in self._device.services.values():
            if not service.subscription_sid:
                continue

            try:
                sid = service.subscription_sid
                if sid:
                    self._notify_view.unregister_service(sid)
                    await service.async_unsubscribe(True)
            except (asyncio.TimeoutError, aiohttp.ClientError):
                pass

    async def _async_init_device(self):
        """Fetch and init services."""
        self._device = await self._factory.async_create_device(self._url)

        # ensure correct UDN
        if self._udn and self._device.udn != self._udn:
            _LOGGER.warning('Given UDN (%s) does not match device UDN: %s',
                            self._udn, self._device.udn)

        # set name
        if self.name is None or self.name == DEFAULT_NAME:
            self._name = self._device.name

        # subscribe services for events
        callback_url = self._notify_view.callback_url
        for service_type, service in self._device.services.items():
            if service_type not in SERVICE_TYPES.values():
                continue

            service.on_state_variable_change = self.on_state_variable_change

            sid = await service.async_subscribe(callback_url)
            if sid:
                self._notify_view.register_service(sid, service)

    async def async_update(self):
        """Retrieve the latest data."""
        if not self._device:
            try:
                await self._async_init_device()
            except (asyncio.TimeoutError, aiohttp.ClientError):
                # Not yet seen alive, leave for now, gracefully
                return

        # call GetTransportInfo/GetPositionInfo regularly
        try:
            avt_service = self._service('AVT')
            if avt_service:
                get_transport_info_action = \
                    avt_service.action('GetTransportInfo')
                state = await self._async_poll_transport_info(
                    get_transport_info_action)
                await asyncio.sleep(0.25)

                if state == STATE_PLAYING or state == STATE_PAUSED:
                    # playing something... get position info
                    get_position_info_action = avt_service.action(
                        'GetPositionInfo')
                    await self._async_poll_position_info(
                        get_position_info_action)
            else:
                await self._device.async_ping()

            self._is_connected = True
        except (asyncio.TimeoutError, aiohttp.ClientError) as ex:
            _LOGGER.debug('%s.async_update(): error on update: %s', self, ex)
            self._is_connected = False
            await self.async_unsubscribe_all()

    async def _async_poll_transport_info(self, action):
        """Update transport info from device."""
        result = await action.async_call(InstanceID=0)

        # set/update state_variable 'TransportState'
        service = action.service
        state_var = service.state_variable('TransportState')
        old_value = state_var.value
        state_var.value = result['CurrentTransportState']

        if old_value != result['CurrentTransportState']:
            self.on_state_variable_change(service, [state_var])

        return self.state

    async def _async_poll_position_info(self, action):
        """Update position info."""
        result = await action.async_call(InstanceID=0)

        service = action.service
        track_duration = service.state_variable('CurrentTrackDuration')
        track_duration.value = result['TrackDuration']

        time_position = service.state_variable('RelativeTimePosition')
        time_position.value = result['RelTime']

        self.on_state_variable_change(service, [track_duration, time_position])

    def on_state_variable_change(self, service, state_variables):
        """State variable(s) changed, let home-assistant know."""
        for state_variable in state_variables:
            if state_variable.name == 'LastChange':
                from async_upnp_client.utils import \
                    dlna_handle_notify_last_change
                dlna_handle_notify_last_change(state_variable)

        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_DLNA_DMR

    @property
    @requires_state_variable('RC', 'Volume')
    def volume_level(self, state_variable):
        """Volume level of the media player (0..1)."""
        # pylint: disable=arguments-differ
        value = state_variable.value
        if value is None:
            _LOGGER.debug('%s.volume_level(): Got no value', self)
            return None

        max_value = state_variable.max_value or 100
        return min(value / max_value, 1.0)

    @requires_action('RC', 'SetVolume')
    async def async_set_volume_level(self, action, volume):
        """Set volume level, range 0..1."""
        # pylint: disable=arguments-differ
        argument = action.argument('DesiredVolume')
        state_variable = argument.related_state_variable
        min_ = state_variable.min_value or 0
        max_ = state_variable.max_value or 100
        desired_volume = int(min_ + volume * (max_ - min_))

        await action.async_call(InstanceID=0,
                                Channel='Master',
                                DesiredVolume=desired_volume)

    @property
    @requires_state_variable('RC', 'Mute')
    def is_volume_muted(self, state_variable):
        """Boolean if volume is currently muted."""
        # pylint: disable=arguments-differ
        value = state_variable.value
        if value is None:
            _LOGGER.debug('%s.is_volume_muted(): Got no value', self)
            return None

        return value

    @requires_action('RC', 'SetMute')
    async def async_mute_volume(self, action, mute):
        """Mute the volume."""
        # pylint: disable=arguments-differ
        desired_mute = bool(mute)
        await action.async_call(InstanceID=0,
                                Channel='Master',
                                DesiredMute=desired_mute)

    @requires_action('AVT', 'Pause')
    async def async_media_pause(self, action):
        """Send pause command."""
        # pylint: disable=arguments-differ
        await action.async_call(InstanceID=0)

    @requires_action('AVT', 'Play')
    async def async_media_play(self, action):
        """Send play command."""
        # pylint: disable=arguments-differ
        await action.async_call(InstanceID=0, Speed='1')

    @requires_action('AVT', 'Stop')
    async def async_media_stop(self, action):
        """Send stop command."""
        # pylint: disable=arguments-differ
        await action.async_call(InstanceID=0)

    @requires_action('AVT', 'SetAVTransportURI')
    async def async_play_media(self, action, media_type, media_id, **kwargs):
        """Play a piece of media."""
        # pylint: disable=arguments-differ

        # queue media
        meta_data = await self._construct_play_media_metadata(media_type,
                                                              media_id)
        await action.async_call(InstanceID=0,
                                CurrentURI=media_id,
                                CurrentURIMetaData=meta_data)
        await asyncio.sleep(0.25)

        # send play command
        await self.async_media_play()
        await asyncio.sleep(0.25)

    async def _construct_play_media_metadata(self, media_type, media_id):
        """Construct the metadata for play_media command."""
        media_info = {
            'mime_type': HOME_ASSISTANT_UPNP_MIME_TYPE_MAPPING[media_type],
            'dlna_features': 'DLNA.ORG_OP=01;DLNA.ORG_CI=0;'
                             'DLNA.ORG_FLAGS=00000000000000000000000000000000',
        }

        # do a HEAD/GET, to retrieve content-type/mime-type
        try:
            req_src_headers = {
                'GetContentFeatures.dlna.org': '1'
            }
            src_headers = await fetch_headers(self.hass,
                                              media_id,
                                              req_src_headers)

            if 'Content-Type' in src_headers:
                media_info['mime_type'] = src_headers['Content-Type']

            if 'ContentFeatures.dlna.org' in media_info:
                media_info['dlna_features'] = \
                    src_headers['contentFeatures.dlna.org']
        except aiohttp.ClientError:
            pass

        # build DIDL-Lite item + resource
        upnp_class = HOME_ASSISTANT_UPNP_CLASS_MAPPING[media_type]

        from didl_lite import didl_lite
        protocol_info = "http-get:*:{mime_type}:{dlna_features}".format(
            **media_info)
        resource = didl_lite.Resource(uri=media_id,
                                      protocol_info=protocol_info)
        item_type = didl_lite.type_by_upnp_class(upnp_class)
        item = item_type(id="0", parent_id="0", title="Home Assistant",
                         restricted="1", resources=[resource])

        return didl_lite.to_xml_string(item).decode('utf-8')

    @requires_action('AVT', 'Previous')
    async def async_media_previous_track(self, action):
        """Send previous track command."""
        # pylint: disable=arguments-differ
        await action.async_call(InstanceID=0)

    @requires_action('AVT', 'Next')
    async def async_media_next_track(self, action):
        """Send next track command."""
        # pylint: disable=arguments-differ
        await action.async_call(InstanceID=0)

    @property
    @requires_state_variable('AVT', 'CurrentTrackMetaData')
    def media_title(self, state_variable):
        """Title of current playing media."""
        # pylint: disable=arguments-differ
        xml = state_variable.value
        if not xml:
            return None

        from didl_lite import didl_lite
        items = didl_lite.from_xml_string(xml)
        if not items:
            return None

        item = items[0]
        return item.title

    @property
    @requires_state_variable('AVT', 'CurrentTrackMetaData')
    def media_image_url(self, state_variable):
        """Image url of current playing media."""
        # pylint: disable=arguments-differ
        xml = state_variable.value
        if not xml:
            return None

        from didl_lite import didl_lite
        items = didl_lite.from_xml_string(xml)
        if not items or not items[0].resources:
            return None
        item = items[0]
        for res in item.resources:
            protocol_info = res.protocol_info
            if protocol_info.startswith('http-get:*:image/'):
                return res.url

        return None

    @property
    def state(self):
        """State of the player."""
        if not self._is_connected:
            return STATE_OFF

        avt_service = self._service('AVT')
        if not avt_service:
            return STATE_ON

        transport_state = avt_service.state_variable('TransportState')
        if not transport_state:
            return STATE_ON
        elif transport_state.value == 'PLAYING':
            return STATE_PLAYING
        elif transport_state.value == 'PAUSED_PLAYBACK':
            return STATE_PAUSED

        return STATE_IDLE

    @property
    @requires_state_variable('AVT', 'CurrentTrackDuration')
    def media_duration(self, state_variable):
        """Duration of current playing media in seconds."""
        # pylint: disable=arguments-differ
        if state_variable is None or \
           state_variable.value is None or \
           state_variable.value == 'NOT_IMPLEMENTED':
            return None

        split = [int(v) for v in re.findall(r"[\w']+", state_variable.value)]
        delta = timedelta(hours=split[0], minutes=split[1], seconds=split[2])
        return delta.seconds

    @property
    @requires_state_variable('AVT', 'RelativeTimePosition')
    def media_position(self, state_variable):
        """Position of current playing media in seconds."""
        # pylint: disable=arguments-differ
        if state_variable is None or \
           state_variable.value is None or \
           state_variable.value == 'NOT_IMPLEMENTED':
            return None

        split = [int(v) for v in re.findall(r"[\w']+", state_variable.value)]
        delta = timedelta(hours=split[0], minutes=split[1], seconds=split[2])
        return delta.seconds

    @property
    @requires_state_variable('AVT', 'RelativeTimePosition')
    def media_position_updated_at(self, state_variable):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        # pylint: disable=arguments-differ
        return state_variable.updated_at

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        if not self._udn:
            return None

        return "{}.{}".format(__name__, self._udn)

    def __str__(self):
        """To string."""
        return "<DlnaDmrDevice('{}')>".format(self._udn)
