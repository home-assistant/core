"""
This platform provides support to streaming any camera supported by Camect
Home using WebRTC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.camect/
"""
import asyncio
from contextlib import suppress
import logging
from typing import Dict

import aiohttp
from aiohttp import web
import async_timeout

from homeassistant.components import camect, camera
from homeassistant.components.http import HomeAssistantView

REQUIREMENTS = ['camect-py==0.1.0']
DEPENDENCIES = ['camect']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, cam_ids):
    """Add an entity for every camera from Camect Home."""
    component = hass.data[camera.DOMAIN]
    hass.http.register_view(CamectWebsocketView(component))
    hass.http.register_view(CamectBundleJsView())
    hass.http.register_view(CamectFontFileView())

    home = hass.data[camect.DOMAIN]
    camect_site = home.get_cloud_url('')
    cam_jsons = home.list_cameras()
    if cam_jsons:
        cams = []
        for cj in cam_jsons:
            if not cam_ids or cj['id'] in cam_ids:
                cams.append(Camera(cj, camect_site))
        add_entities(cams, True)
    return True


class Camera(camera.Camera):
    """An implementation of a camera supported by Camect Home."""

    def __init__(self, json: Dict[str, str], camect_site: str):
        """Initialize a camera supported by Camect Home."""
        super(Camera, self).__init__()
        self._device_id = json['id']
        self._id = '{}_{}'.format(camect.DOMAIN, self._device_id)
        self.entity_id = '{}.{}'.format(camect.DOMAIN, self._id)
        self._name = json['name']
        self._make = json['make'] or ''
        self._model = json['model'] or ''
        self._url = json['url']
        self._width = int(json['width'])
        self._height = int(json['height'])
        self._camect_site = camect_site

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def brand(self):
        """Return the camera brand."""
        return self._make

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return True

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def entity_picture(self):
        """Return a link to the camera feed as entity picture."""
        return None

    def camera_image(self):
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'device_id': self._device_id,
            'device_url': self._url,
            'video_width': self._width,
            'video_height': self._height,
            'camect_site': self._camect_site,
        }

    @property
    def should_poll(self):
        """No need for the poll."""
        return False


class CamectWebsocketView(camera.CameraView):
    """Camect view to proxy Websocket to home."""

    url = '/api/camect_proxy/websocket/{entity_id}'
    name = 'api:camect:websocket'

    async def handle(self, request, camera):
        """Serve Camect Websocket."""
        ha_ws = web.WebSocketResponse()
        await ha_ws.prepare(request)

        hass = request.app['hass']
        home = hass.data[camect.DOMAIN]
        ws_url = home.get_unsecure_websocket_url()
        if not ws_url:
            raise web.HTTPInternalServerError()
        session = aiohttp.ClientSession()
        camect_ws = await session.ws_connect(ws_url, ssl=False)

        async def forward(src, dst):
            async for msg in src:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await dst.send_bytes(msg.data)
                else:
                    _LOGGER.warning(
                        "Received invalid message type: %s", msg.type)
        await asyncio.gather(
            forward(ha_ws, camect_ws), forward(camect_ws, ha_ws))

        ha_ws.close()
        camect_ws.close()


async def _unsecure_https_fetch(https_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(https_url, verify_ssl=False) as resp:
            if resp.status != 200:
                _LOGGER.warning('resp.status=%d', resp.status)
                return ''
            return await resp.read()


class CamectBundleJsView(HomeAssistantView):
    """Camect view to proxy embedded bundle JS to home."""

    url = '/api/camect_proxy/bundle.js'
    name = 'api:camect:bundlejs'
    requires_auth = False

    async def get(self, request):
        """Serve Camect embedded bundle JS."""
        from camect import EMBEDDED_BUNDLE_JS

        hass = request.app['hass']
        home = hass.data[camect.DOMAIN]

        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=request.app['hass'].loop):
                js_url = home.get_unsecure_https_url(EMBEDDED_BUNDLE_JS)
                if not js_url:
                    raise web.HTTPInternalServerError()
                data = await hass.async_add_job(_unsecure_https_fetch, js_url)
                if data:
                    return web.Response(
                        body=data, content_type="application/javascript")

        raise web.HTTPInternalServerError()


class CamectFontFileView(HomeAssistantView):
    """Camect view to proxy font files to home."""

    url = '/api/camect_proxy/font/{font_file}'
    name = 'api:camect:font'
    requires_auth = False

    async def get(self, request, font_file):
        """Serve Camect font files."""
        hass = request.app['hass']
        home = hass.data[camect.DOMAIN]

        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=request.app['hass'].loop):
                font_url = home.get_unsecure_https_url('font/' + font_file)
                if not font_url:
                    raise web.HTTPInternalServerError()
                data = await hass.async_add_job(
                    _unsecure_https_fetch, font_url)
                if data:
                    if font_file.endswith('.css'):
                        return web.Response(body=data, content_type="text/css")
                    return web.Response(body=data)

        raise web.HTTPInternalServerError()
