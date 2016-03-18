# pylint: disable=too-many-lines
"""
Component to interface with cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera/
"""
import logging
import re
import time

import requests

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components import bloomsky
from homeassistant.const import (
    HTTP_NOT_FOUND,
    ATTR_ENTITY_ID,
    )


DOMAIN = 'camera'
DEPENDENCIES = ['http']
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    bloomsky.DISCOVER_CAMERAS: 'bloomsky',
}

STATE_RECORDING = 'recording'
STATE_STREAMING = 'streaming'
STATE_IDLE = 'idle'

ENTITY_IMAGE_URL = '/api/camera_proxy/{0}'

MULTIPART_BOUNDARY = '--jpegboundary'
MJPEG_START_HEADER = 'Content-type: {0}\r\n\r\n'


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup the camera component."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    # -------------------------------------------------------------------------
    # CAMERA COMPONENT ENDPOINTS
    # -------------------------------------------------------------------------
    # The following defines the endpoints for serving images from the camera
    # via the HA http server.  This is means that you can access images from
    # your camera outside of your LAN without the need for port forwards etc.

    # Because the authentication header can't be added in image requests these
    # endpoints are secured with session based security.

    # pylint: disable=unused-argument
    def _proxy_camera_image(handler, path_match, data):
        """Serve the camera image via the HA server."""
        entity_id = path_match.group(ATTR_ENTITY_ID)
        camera = component.entities.get(entity_id)

        if camera is None:
            handler.send_response(HTTP_NOT_FOUND)
            handler.end_headers()
            return

        response = camera.camera_image()

        if response is None:
            handler.send_response(HTTP_NOT_FOUND)
            handler.end_headers()
            return

        handler.wfile.write(response)

    hass.http.register_path(
        'GET',
        re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_image)

    # pylint: disable=unused-argument
    def _proxy_camera_mjpeg_stream(handler, path_match, data):
        """
        Proxy the camera image as an mjpeg stream via the HA server.

        This function takes still images from the IP camera and turns them
        into an MJPEG stream.  This means that HA can return a live video
        stream even with only a still image URL available.
        """
        entity_id = path_match.group(ATTR_ENTITY_ID)
        camera = component.entities.get(entity_id)

        if camera is None:
            handler.send_response(HTTP_NOT_FOUND)
            handler.end_headers()
            return

        try:
            camera.is_streaming = True
            camera.update_ha_state()
            camera.mjpeg_stream(handler)

        except (requests.RequestException, IOError):
            camera.is_streaming = False
            camera.update_ha_state()

    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/camera_proxy_stream/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_mjpeg_stream)

    return True


class Camera(Entity):
    """The base class for camera entities."""

    def __init__(self):
        """Initialize a camera."""
        self.is_streaming = False

    @property
    def should_poll(self):
        """No need to poll cameras."""
        return False

    @property
    def entity_picture(self):
        """Return a link to the camera feed as entity picture."""
        return ENTITY_IMAGE_URL.format(self.entity_id)

    @property
    # pylint: disable=no-self-use
    def is_recording(self):
        """Return true if the device is recording."""
        return False

    @property
    # pylint: disable=no-self-use
    def brand(self):
        """Camera brand."""
        return None

    @property
    # pylint: disable=no-self-use
    def model(self):
        """Camera model."""
        return None

    def camera_image(self):
        """Return bytes of camera image."""
        raise NotImplementedError()

    def mjpeg_stream(self, handler):
        """Generate an HTTP MJPEG stream from camera images."""
        handler.request.sendall(bytes('HTTP/1.1 200 OK\r\n', 'utf-8'))
        handler.request.sendall(bytes(
            'Content-type: multipart/x-mixed-replace; \
                boundary=--jpgboundary\r\n\r\n', 'utf-8'))
        handler.request.sendall(bytes('--jpgboundary\r\n', 'utf-8'))

        # MJPEG_START_HEADER.format()
        while True:
            img_bytes = self.camera_image()
            if img_bytes is None:
                continue
            headers_str = '\r\n'.join((
                'Content-length: {}'.format(len(img_bytes)),
                'Content-type: image/jpeg',
            )) + '\r\n\r\n'

            handler.request.sendall(
                bytes(headers_str, 'utf-8') +
                img_bytes +
                bytes('\r\n', 'utf-8'))

            handler.request.sendall(
                bytes('--jpgboundary\r\n', 'utf-8'))

            time.sleep(0.5)

    @property
    def state(self):
        """Camera state."""
        if self.is_recording:
            return STATE_RECORDING
        elif self.is_streaming:
            return STATE_STREAMING
        else:
            return STATE_IDLE

    @property
    def state_attributes(self):
        """Camera state attributes."""
        attr = {}

        if self.model:
            attr['model_name'] = self.model

        if self.brand:
            attr['brand'] = self.brand

        return attr
