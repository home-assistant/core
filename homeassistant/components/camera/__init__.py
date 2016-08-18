# pylint: disable=too-many-lines
"""
Component to interface with cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/camera/
"""
import logging
import time

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.components.http import HomeAssistantView

DOMAIN = 'camera'
DEPENDENCIES = ['http']
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'

STATE_RECORDING = 'recording'
STATE_STREAMING = 'streaming'
STATE_IDLE = 'idle'

ENTITY_IMAGE_URL = '/api/camera_proxy/{0}?token={1}'


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup the camera component."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    hass.wsgi.register_view(CameraImageView(hass, component.entities))
    hass.wsgi.register_view(CameraMjpegStream(hass, component.entities))

    component.setup(config)

    return True


class Camera(Entity):
    """The base class for camera entities."""

    def __init__(self):
        """Initialize a camera."""
        self.is_streaming = False

    @property
    def access_token(self):
        """Access token for this camera."""
        return str(id(self))

    @property
    def should_poll(self):
        """No need to poll cameras."""
        return False

    @property
    def entity_picture(self):
        """Return a link to the camera feed as entity picture."""
        return ENTITY_IMAGE_URL.format(self.entity_id, self.access_token)

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return False

    @property
    def brand(self):
        """Camera brand."""
        return None

    @property
    def model(self):
        """Camera model."""
        return None

    def camera_image(self):
        """Return bytes of camera image."""
        raise NotImplementedError()

    def mjpeg_stream(self, response):
        """Generate an HTTP MJPEG stream from camera images."""
        def stream():
            """Stream images as mjpeg stream."""
            try:
                last_image = None
                while True:
                    img_bytes = self.camera_image()

                    if img_bytes is not None and img_bytes != last_image:
                        yield bytes(
                            '--jpegboundary\r\n'
                            'Content-Type: image/jpeg\r\n'
                            'Content-Length: {}\r\n\r\n'.format(
                                len(img_bytes)), 'utf-8') + img_bytes + b'\r\n'

                        last_image = img_bytes

                    time.sleep(0.5)
            except GeneratorExit:
                pass

        return response(
            stream(),
            content_type=('multipart/x-mixed-replace; '
                          'boundary=--jpegboundary')
        )

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
        attr = {
            'access_token': self.access_token,
        }

        if self.model:
            attr['model_name'] = self.model

        if self.brand:
            attr['brand'] = self.brand

        return attr


class CameraView(HomeAssistantView):
    """Base CameraView."""

    requires_auth = False

    def __init__(self, hass, entities):
        """Initialize a basic camera view."""
        super().__init__(hass)
        self.entities = entities

    def get(self, request, entity_id):
        """Start a get request."""
        camera = self.entities.get(entity_id)

        if camera is None:
            return self.Response(status=404)

        authenticated = (request.authenticated or
                         request.args.get('token') == camera.access_token)

        if not authenticated:
            return self.Response(status=401)

        return self.handle(camera)

    def handle(self, camera):
        """Hanlde the camera request."""
        raise NotImplementedError()


class CameraImageView(CameraView):
    """Camera view to serve an image."""

    url = "/api/camera_proxy/<entity(domain=camera):entity_id>"
    name = "api:camera:image"

    def handle(self, camera):
        """Serve camera image."""
        response = camera.camera_image()

        if response is None:
            return self.Response(status=500)

        return self.Response(response)


class CameraMjpegStream(CameraView):
    """Camera View to serve an MJPEG stream."""

    url = "/api/camera_proxy_stream/<entity(domain=camera):entity_id>"
    name = "api:camera:stream"

    def handle(self, camera):
        """Serve camera image."""
        return camera.mjpeg_stream(self.Response)
