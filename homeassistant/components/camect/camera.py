"""
This platform provides support to streaming any camera supported by Camect
Home using WebRTC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.camect/
"""
from typing import Dict

from homeassistant.components import camect, camera

DEPENDENCIES = ['camect']


def setup_platform(hass, config, add_entities, cam_ids):
    """Add an entity for every camera from Camect Home."""
    home = hass.data[camect.DOMAIN]
    camect_site = home.get_cloud_url('')
    ws_url = home.get_local_websocket_url()
    cam_jsons = home.list_cameras()
    if cam_jsons:
        cams = []
        for cj in cam_jsons:
            if not cam_ids or cj['id'] in cam_ids:
                cams.append(Camera(home, cj, camect_site, ws_url))
        add_entities(cams, True)
    return True


class Camera(camera.Camera):
    """An implementation of a camera supported by Camect Home."""

    def __init__(self, home, json: Dict[str, str], camect_site: str, ws_url: str):
        """Initialize a camera supported by Camect Home."""
        super(Camera, self).__init__()
        self._home = home
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
        self._ws_url = ws_url

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
        return self._home.snapshot_camera(self._device_id)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'device_id': self._device_id,
            'device_url': self._url,
            'video_width': self._width,
            'video_height': self._height,
            'camect_site': self._camect_site,
            'ws_url': self._ws_url,
        }

    @property
    def should_poll(self):
        """No need for the poll."""
        return False
