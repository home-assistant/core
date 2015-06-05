# pylint: disable=too-many-lines
"""
homeassistant.components.camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various cameras.

The following features are supported:
-Recording
-Snapshot
-Motion Detection Recording(for supported cameras)
-Automatic Configuration(for supported cameras)
-Creation of child entities for supported functions
-Collating motion event images passed via FTP into time based events
-Returning recorded camera images and streams
-Proxying image requests via HA for external access
-Converting a still image url into a live video stream
-A service for calling camera functions

Upcoming features
-Camera movement(panning)
-Zoom
-Light/Nightvision toggling
-Support for more devices
-A demo entity
-Expanded documentation
"""
import requests
from requests.auth import HTTPBasicAuth
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
            response = camera.get_camera_image()
            handler.wfile.write(response)
        else:
            handler.send_response(HTTP_NOT_FOUND)

    hass.http.register_path(
        'GET',
        re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_image,
        require_auth=True)

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

        if camera:

            try:
                camera.is_streaming = True
                camera.update_ha_state()

                handler.request.sendall(bytes('HTTP/1.1 200 OK\r\n', 'utf-8'))
                handler.request.sendall(bytes(
                    'Content-type: multipart/x-mixed-replace; \
                        boundary=--jpgboundary\r\n\r\n', 'utf-8'))

                handler.request.sendall(bytes('--jpgboundary\r\n', 'utf-8'))

                while True:

                    if camera.username and camera.password:
                        response = requests.get(
                            camera.still_image_url,
                            auth=HTTPBasicAuth(
                                camera.username,
                                camera.password))
                    else:
                        response = requests.get(camera.still_image_url)

                    headers_str = '\r\n'.join((
                        'Content-length: {}'.format(len(response.content)),
                        'Content-type: image/jpeg',
                    )) + '\r\n\r\n'

                    handler.request.sendall(
                        bytes(headers_str, 'utf-8') +
                        response.content +
                        bytes('\r\n', 'utf-8'))

                    handler.request.sendall(
                        bytes('--jpgboundary\r\n', 'utf-8'))

            except (requests.RequestException, IOError):
                camera.is_streaming = False
                camera.update_ha_state()

        else:
            handler.send_response(HTTP_NOT_FOUND)

        camera.is_streaming = False

    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/camera_proxy_stream/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _proxy_camera_mjpeg_stream,
        require_auth=True)


class Camera(Entity):
    """ The base class for camera components """

    @property
    # pylint: disable=no-self-use
    def is_recording(self):
        """ Returns true if the device is recording """
        return False

    @property
    # pylint: disable=no-self-use
    def is_streaming(self):
        """ Returns true if the device is streaming """
        return False

    @is_streaming.setter
    def is_streaming(self, value):
        """ Set this to true when streaming begins """
        pass

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

    @property
    # pylint: disable=no-self-use
    def base_url(self):
        """ Return the configured base URL for the camera """
        return None

    @property
    # pylint: disable=no-self-use
    def image_url(self):
        """ Return the still image segment of the URL """
        return None

    @property
    # pylint: disable=no-self-use
    def device_info(self):
        """ Get the configuration object """
        return None

    @property
    # pylint: disable=no-self-use
    def username(self):
        """ Get the configured username """
        return None

    @property
    # pylint: disable=no-self-use
    def password(self):
        """ Get the configured password """
        return None

    @property
    # pylint: disable=no-self-use
    def still_image_url(self):
        """ Get the URL of a camera still image """
        return None

    def get_camera_image(self):
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
        attr = super().state_attributes
        attr['model_name'] = self.device_info.get('model', 'generic')
        attr['brand'] = self.device_info.get('brand', 'generic')
        attr['still_image_url'] = '/api/camera_proxy/' + self.entity_id
        attr[ATTR_ENTITY_PICTURE] = (
            '/api/camera_proxy/' +
            self.entity_id + '?time=' +
            str(time.time()))
        attr['stream_url'] = '/api/camera_proxy_stream/' + self.entity_id

        return attr
