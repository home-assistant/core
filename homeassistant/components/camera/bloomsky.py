"""
homeassistant.components.sensor.bloomsky
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/bloomsky/
"""
import logging
import requests
import homeassistant.components.bloomsky as bloomsky
from homeassistant.components.camera import Camera

DEPENDENCIES = ["bloomsky"]


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ set up access to the BloomSky's camera """
    for device_key in bloomsky.BLOOMSKY.devices:
        device = bloomsky.BLOOMSKY.devices[device_key]
        for variable in config["devices"]:
            if variable == device["DeviceName"]:
                add_devices_callback([BloomSkyCamera(bloomsky.BLOOMSKY,
                                                     device)])


class BloomSkyCamera(Camera):
    """ Represents the images published from the BloomSky's camera """

    def __init__(self, bs, device):
        """ set up for access to the BloomSky camera images """
        super(BloomSkyCamera, self).__init__()
        self._name = device["DeviceName"]
        self._id = device["DeviceID"]
        self._bloomsky = bs
        self._url = ""
        self._last_url = ""
        # _last_image will store images as they are downloaded so that the
        # frequent updates in home-assistant don't keep poking the server
        # to download the same image over and over
        self._last_image = ""
        self._logger = logging.getLogger(__name__)

    def camera_image(self):
        """ update the camera's image if it has changed """
        try:
            self._url = self._bloomsky.devices[self._id]["Data"]["ImageURL"]
            self._bloomsky.refresh_devices()
            # if the url hasn't changed then the image hasn't changed
            if self._url != self._last_url:
                response = requests.get(self._url)
                self._last_url = self._url
                self._last_image = response.content
        except requests.exceptions.RequestException as error:
            self._logger.error("Error getting bloomsky image: {}"
                               .format(error))
            return None

        return self._last_image

    @property
    def name(self):
        """ the name of this BloomSky device """
        return self._name
