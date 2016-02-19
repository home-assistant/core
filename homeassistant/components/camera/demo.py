"""
homeassistant.components.camera.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that has a fake camera.
"""
import os

import homeassistant.util.dt as dt_util
from homeassistant.components.camera import Camera


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo camera. """
    add_devices([
        DemoCamera('Demo camera')
    ])


class DemoCamera(Camera):
    """ A Demo camera. """

    def __init__(self, name):
        super().__init__()
        self._name = name

    def camera_image(self):
        """ Return a faked still image response. """
        now = dt_util.utcnow()

        image_path = os.path.join(os.path.dirname(__file__),
                                  'demo_{}.jpg'.format(now.second % 4))
        with open(image_path, 'rb') as file:
            return file.read()

    @property
    def name(self):
        """ Return the name of this device. """
        return self._name
