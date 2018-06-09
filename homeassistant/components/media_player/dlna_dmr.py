# -*- coding: utf-8 -*-
"""Support for DLNA DMR (Device Media Renderer)."""

import asyncio
import functools
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession


REQUIREMENTS = ['async-upnp-client==0.10.0']

DEFAULT_NAME = 'DLNA_DMR'
CONF_MAX_VOLUME = 'max_volume'
CONF_PICKY_DEVICE = 'picky_device'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_MAX_VOLUME): cv.positive_int,
    vol.Optional(CONF_PICKY_DEVICE): cv.boolean,
})

NS = {
    'didl_lite': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

SERVICE_TYPES = {
    'RC': 'urn:schemas-upnp-org:service:RenderingControl:1',
    'AVT': 'urn:schemas-upnp-org:service:AVTransport:1',
}

DIDL_TEMPLATE = """
<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
           xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
           xmlns:dc="http://purl.org/dc/elements/1.1/"
           xmlns:sec="http://www.sec.co.kr/">
<item id="0" parentID="0" restricted="1">
  <dc:title>Home Assistant</dc:title>
  <upnp:class>{upnp_class}</upnp:class>
  <res protocolInfo="http-get:*:{mime_type}:{dlna_features}">{media_url}</res>
</item>
</DIDL-Lite>"""

HOME_ASSISTANT_UPNP_CLASS_MAPPING = {
    'music': 'object.item.audioItem',
    'tvshow': 'object.item.videoItem',
    'video': 'object.item.videoItem',
    'episode': 'object.item.videoItem',
    'channel': 'object.item.videoItem',
    'playlist': 'object.item.playlist',
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
        return hass_data[name]

    view = UpnpNotifyView(hass)
    hass_data[name] = view
    hass.http.register_view(view)
    return view


def start_proxy_view(hass):
    """Register proxy view."""
    hass_data = hass.data[__name__]
    name = 'proxy_view'
    if name in hass_data:
        return hass_data[name]

    view = PickyDeviceProxyView(hass)
    hass_data[name] = view
    hass.http.register_view(view)
    return view


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up DLNA DMR platform."""
    if discovery_info and \
       'upnp_device_type' in discovery_info and \
       discovery_info['upnp_device_type'] != UPNP_DEVICE_MEDIA_RENDERER:
        _LOGGER.debug('Device is not a MediaRenderer: %s',
                      discovery_info.get('ssdp_description'))
        return

    is_picky = False
    if config.get(CONF_URL) is not None:
        url = config.get(CONF_URL)
        name = config.get(CONF_NAME)
    elif discovery_info is not None:
        url = discovery_info['ssdp_description']
        name = discovery_info['name']

        # Samsung TVs are particular picky with regard to their sources
        manufacturer = discovery_info.get('manufacturer', '').lower()
        is_samsung = 'samsung' in manufacturer
        is_tv = 'tv' in discovery_info.get('name', '').lower()
        is_picky = is_samsung and is_tv

    cfg_extra = {
        CONF_MAX_VOLUME: config.get(CONF_MAX_VOLUME),
        CONF_PICKY_DEVICE: config.get(CONF_PICKY_DEVICE) or is_picky,
    }

    # set up our Views, if not already done so
    if __name__ not in hass.data:
        hass.data[__name__] = {}

    hass.async_run_job(start_notify_view, hass)
    hass.async_run_job(start_proxy_view, hass)

    from async_upnp_client import UpnpFactory
    requester = HassUpnpRequester(hass)
    factory = UpnpFactory(requester)
    device = DlnaDmrDevice(hass, url, name, factory, **cfg_extra)

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
            return aiohttp.web.Response(status=422)

        headers = request.headers
        sid = headers['SID']
        body = await request.text()

        # find UpnpService by SID
        if sid not in self._registered_services:
            self._backlog[sid] = {'headers': headers, 'body': body}
            return aiohttp.web.Response(status=202)

        service = self._registered_services[sid]
        service.on_notify(headers, body)
        return aiohttp.web.Response(status=200)

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
            service.on_notify(item['headers'], item['body'])
            del self._backlog[sid]

    def unregister_service(self, sid):
        """Unregister service by SID."""
        if sid in self._registered_services:
            del self._registered_services[sid]


class PickyDeviceProxyView(HomeAssistantView):
    """View to serve device media."""

    url = '/api/dlna_dmr.proxy/{key}'
    proxy_path = '/api/dlna_dmr.proxy'

    name = 'api:dlna_dmr:proxy'
    requires_auth = False

    DLNA_CONTENT_FEATURES = \
        'DLNA.ORG_OP=01;' \
        'DLNA.ORG_CI=0;' \
        'DLNA.ORG_FLAGS=01700000000000000000000000000000'
    DLNA_TRANSFER_MODE = 'Streaming'

    def __init__(self, hass):
        """Initializer."""
        self.hass = hass
        self._entries = {}

    def register(self, router):
        """Register the view with a router."""
        handler = request_handler_factory(self, self.async_head)
        router.add_route('head', self.url, handler)

        handler = request_handler_factory(self, self.async_get)
        router.add_route('get', self.url, handler)

    def _prune_entries(self):
        """Prune entries older than 24 hours."""
        max_age = timedelta(hours=24)
        now = datetime.now()

        to_remove = []
        for key, entry in self._entries.items():
            age = now - entry['added_at']
            if age > max_age:
                to_remove.append(key)

        for key in to_remove:
            del self._entries[key]

    def add_url(self, url):
        """Add a new URL to the proxy, valid for 24 hours."""
        self._prune_entries()

        import hashlib
        key = hashlib.sha256(url.encode('utf-8')).hexdigest()

        self._entries[key] = {
            'url': url,
            'added_at': datetime.now(),
        }

        return key

    @property
    def callback_url(self):
        """Full URL to be called by device/service."""
        base_url = self.hass.config.api.base_url
        return urllib.parse.urljoin(base_url, self.url)

    async def async_head(self, request, **args):
        """Handle HEAD request."""
        url = None
        if 'key' in args:
            key = args['key']
            entry = self._entries[key]
            url = entry['url']
        else:
            return aiohttp.web.Response(body="Missing URL", status=422)

        src_headers = await fetch_headers(self.hass, url, request.headers)
        headers = {
            'Accept-Ranges': 'bytes',
            'transferMode.dlna.org': self.DLNA_TRANSFER_MODE,
            'contentFeatures.dlna.org': self.DLNA_CONTENT_FEATURES,
        }
        headers.update(src_headers)
        return aiohttp.web.Response(headers=headers)

    async def async_get(self, request, **args):
        """Handle GET request."""
        url = None
        if 'key' in args:
            key = args['key']
            entry = self._entries[key]
            url = entry['url']
        else:
            return aiohttp.web.Response(body="Missing URL", status=422)

        # get data from source
        session = async_get_clientsession(self.hass)
        src_response = await session.get(url, headers=request.headers)
        src_data = await src_response.read()

        headers = {
            'Accept-Ranges': 'bytes',
            'transferMode.dlna.org': self.DLNA_TRANSFER_MODE,
            'contentFeatures.dlna.org': self.DLNA_CONTENT_FEATURES,
        }
        headers.update(src_response.headers)

        if 'range' in request.headers:
            range_ = request.headers['range']
            parts = [int(x)
                     for x in range_.replace('bytes=', '').split('-')
                     if x]
            from_ = parts[0]
            to_ = parts[1] if len(parts) == 2 else len(src_data)
            chunk_size = (to_ - from_)
            headers['Content-Range'] = 'bytes {}-{}/{}'.format(from_,
                                                               to_,
                                                               len(src_data))
            headers['Content-Length'] = str(chunk_size)
            src_data = src_data[from_:to_]
            return aiohttp.web.Response(body=src_data,
                                        status=206,
                                        headers=headers)

        return aiohttp.web.Response(body=src_data,
                                    status=200,
                                    headers=headers)


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

    def __init__(self, hass, url, name, factory, **additional_configuration):
        """Initializer."""
        self.hass = hass
        self._url = url
        self._name = name
        self._factory = factory
        self._additional_configuration = additional_configuration

        self._notify_view = hass.data[__name__]['notify_view']

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

        # set name
        if self.name is None or self.name == DEFAULT_NAME:
            self._name = self._device.name

        # subscribe services for events
        callback_url = self._notify_view.callback_url
        for service in self._device.services.values():
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
        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported_features = 0

        if not self._device:
            return supported_features

        rc_service = self._service('RC')
        if rc_service:
            if rc_service.state_variable('Mute'):
                supported_features |= SUPPORT_VOLUME_MUTE
            if rc_service.state_variable('Volume'):
                supported_features |= SUPPORT_VOLUME_SET

        avt_service = self._service('AVT')
        if avt_service:
            state_var = avt_service.state_variable('CurrentTransportActions')
            if state_var:
                value = state_var.value or ''
                actions = value.split(',')
                if 'Play' in actions:
                    supported_features |= SUPPORT_PLAY
                if 'Stop' in actions:
                    supported_features |= SUPPORT_STOP
                if 'Pause' in actions:
                    supported_features |= SUPPORT_PAUSE

            current_track_var = avt_service.state_variable('CurrentTrack')
            num_tracks_var = avt_service.state_variable('NumberOfTracks')
            if current_track_var and \
               num_tracks_var and \
               current_track_var.value is not None and \
               num_tracks_var.value is not None:
                current_track = current_track_var.value
                num_tracks = num_tracks_var.value
                if current_track > 1:
                    supported_features |= SUPPORT_PREVIOUS_TRACK

                if num_tracks > current_track:
                    supported_features |= SUPPORT_NEXT_TRACK

            play_media_action = avt_service.action('SetAVTransportURI')
            play_action = avt_service.action('Play')
            if play_media_action and play_action:
                supported_features |= SUPPORT_PLAY_MEDIA

        return supported_features

    @property
    @requires_state_variable('RC', 'Volume')
    def volume_level(self, state_variable):
        """Volume level of the media player (0..1)."""
        # pylint: disable=arguments-differ
        value = state_variable.value
        if value is None:
            _LOGGER.debug('%s.volume_level(): Got no value', self)
            return None

        override_max = self._additional_configuration.get('max_volume', None)
        max_value = override_max or state_variable.max_value or 100
        return min(value / max_value, 1.0)

    @requires_action('RC', 'SetVolume')
    async def async_set_volume_level(self, action, volume):
        """Set volume level, range 0..1."""
        # pylint: disable=arguments-differ
        argument = action.argument('DesiredVolume')
        state_variable = argument.related_state_variable
        min_ = state_variable.min_value or 0
        override_max = self._additional_configuration.get('max_volume', None)
        max_ = override_max or state_variable.max_value or 100
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
        picky_device = self._additional_configuration.get(CONF_PICKY_DEVICE,
                                                          False)
        media_info = {
            'media_url': media_id,
            'upnp_class': HOME_ASSISTANT_UPNP_CLASS_MAPPING[media_type],
        }

        src_headers = None
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

        is_dlna_source = src_headers and \
            'contentFeatures.dlna.org' in src_headers
        if not is_dlna_source:
            if picky_device:
                _LOGGER.debug('%s.async_play_media(): detected invalid source,'
                              ' routing through proxy', self)

                # get proxy url
                proxy_view = self.hass.data[__name__]['proxy_view']
                base_url = self.hass.config.api.base_url
                proxy_url = urllib.parse.urljoin(
                    base_url,
                    PickyDeviceProxyView.proxy_path)

                key = proxy_view.add_url(media_id)
                media_info['media_url'] = '{}/{}'.format(proxy_url, key)
                media_info['dlna_features'] = \
                    PickyDeviceProxyView.DLNA_CONTENT_FEATURES
            else:
                media_info['dlna_features'] = \
                    PickyDeviceProxyView.DLNA_CONTENT_FEATURES.replace('17',
                                                                       '00')

        meta_data = DIDL_TEMPLATE.format(**media_info)
        await action.async_call(InstanceID=0,
                                CurrentURI=media_id,
                                CurrentURIMetaData=meta_data)
        await asyncio.sleep(0.25)

        # send play command
        await self.async_media_play()
        await asyncio.sleep(0.25)

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

        root = ET.fromstring(xml)
        title_xml = root.find('.//dc:title', NS)
        if title_xml is None:
            return None

        return title_xml.text

    @property
    @requires_state_variable('AVT', 'CurrentTrackMetaData')
    def media_image_url(self, state_variable):
        """Image url of current playing media."""
        # pylint: disable=arguments-differ
        xml = state_variable.value
        if not xml:
            return None

        root = ET.fromstring(xml)
        for res in root.findall('.//didl_lite:res', NS):
            protocol_info = res.attrib.get('protocolInfo') or ''
            if protocol_info.startswith('http-get:*:image/'):
                url = protocol_info.text
                return url

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
        if state_variable is None or state_variable.value is None:
            return None

        split = [int(v) for v in re.findall(r"[\w']+", state_variable.value)]
        delta = timedelta(hours=split[0], minutes=split[1], seconds=split[2])
        return delta.seconds

    @property
    @requires_state_variable('AVT', 'RelativeTimePosition')
    def media_position(self, state_variable):
        """Position of current playing media in seconds."""
        # pylint: disable=arguments-differ
        if state_variable is None or state_variable.value is None:
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
        return "{}.{}".format(__name__, self._url)

    def __str__(self):
        """To string."""
        return "<DlnaDmrDevice('{}')>".format(self._url)
