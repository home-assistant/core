# pylint: disable=too-many-lines
"""
homeassistant.components.camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various cameras.

The following features are supported:
 - Returning recorded camera images and streams
 - Proxying image requests via HA for external access
 - Converting a still image url into a live video stream

Upcoming features
 - Recording
 - Snapshot
 - Motion Detection Recording(for supported cameras)
 - Automatic Configuration(for supported cameras)
 - Creation of child entities for supported functions
 - Collating motion event images passed via FTP into time based events
 - A service for calling camera functions
 - Camera movement(panning)
 - Zoom
 - Light/Nightvision toggling
 - Support for more devices
 - Expanded documentation
"""
import requests
import logging
import time
import re
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    HTTP_NOT_FOUND,
    ATTR_ENTITY_ID,
    )

from homeassistant.helpers.entity_component import EntityComponent


DOMAIN = 'camera'
DEPENDENCIES = ['http']
GROUP_NAME_ALL_CAMERAS = 'all_cameras'
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'

SWITCH_ACTION_RECORD = 'record'
SWITCH_ACTION_SNAPSHOT = 'snapshot'

SERVICE_CAMERA = 'camera_service'

STATE_RECORDING = 'recording'

DEFAULT_RECORDING_SECONDS = 30

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}

FILE_DATETIME_FORMAT = '%Y-%m-%d_%H-%M-%S-%f'
DIR_DATETIME_FORMAT = '%Y-%m-%d_%H-%M-%S'

REC_DIR_PREFIX = 'recording-'
REC_IMG_PREFIX = 'recording_image-'

STATE_STREAMING = 'streaming'
STATE_IDLE = 'idle'

CAMERA_PROXY_URL = '/api/camera_proxy_stream/{0}'
CAMERA_STILL_URL = '/api/camera_proxy/{0}'
ENTITY_IMAGE_URL = '/api/camera_proxy/{0}?time={1}'

MULTIPART_BOUNDARY = '--jpegboundary'
MJPEG_START_HEADER = 'Content-type: {0}\r\n\r\n'


# pylint: disable=too-many-branches
def setup(hass, config):
    """ Track states and offer events for sensors. """

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
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group(ATTR_ENTITY_ID)

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            response = camera.camera_image()
            handler.wfile.write(response)
        else:
            handler.send_response(HTTP_NOT_FOUND)

    hass.http.register_path(
        'GET',
        re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_image)

    # pylint: disable=unused-argument
    def _proxy_camera_mjpeg_stream(handler, path_match, data):
        """ Proxies the camera image as an mjpeg stream via the HA server.
        This function takes still images from the IP camera and turns them
        into an MJPEG stream.  This means that HA can return a live video
        stream even with only a still image URL available.
        """
        entity_id = path_match.group(ATTR_ENTITY_ID)

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if not camera:
            handler.send_response(HTTP_NOT_FOUND)
            handler.end_headers()
            return

        try:
            camera.is_streaming = True
            camera.update_ha_state()

            handler.request.sendall(bytes('HTTP/1.1 200 OK\r\n', 'utf-8'))
            handler.request.sendall(bytes(
                'Content-type: multipart/x-mixed-replace; \
                    boundary=--jpgboundary\r\n\r\n', 'utf-8'))
            handler.request.sendall(bytes('--jpgboundary\r\n', 'utf-8'))

            # MJPEG_START_HEADER.format()

            while True:

                img_bytes = camera.camera_image()

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

        except (requests.RequestException, IOError):
            camera.is_streaming = False
            camera.update_ha_state()

        camera.is_streaming = False

    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/camera_proxy_stream/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_mjpeg_stream)

    return True


class Camera(Entity):
    """ The base class for camera components """

    def __init__(self):
        self.is_streaming = False

    @property
    # pylint: disable=no-self-use
    def is_recording(self):
        """ Returns true if the device is recording """
        return False

    @property
    # pylint: disable=no-self-use
    def brand(self):
        """ Should return a string of the camera brand """
        return None

    @property
    # pylint: disable=no-self-use
    def model(self):
        """ Returns string of camera model """
        return None

    def camera_image(self):
        """ Return bytes of camera image """
        raise NotImplementedError()

    @property
    def state(self):
        """ Returns the state of the entity. """
        if self.is_recording:
            return STATE_RECORDING
        elif self.is_streaming:
            return STATE_STREAMING
        else:
            return STATE_IDLE

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = {
            ATTR_ENTITY_PICTURE: ENTITY_IMAGE_URL.format(
                self.entity_id, time.time()),
        }

        if self.model:
            attr['model_name'] = self.model

        if self.brand:
            attr['brand'] = self.brand

        return attr
