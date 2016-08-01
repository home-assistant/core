"""
Support for Amcrest cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.amcrest/
"""
import logging

import requests

from homeassistant.components.camera import DOMAIN, Camera
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Discover cameras on a Unifi NVR."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['ip', 'username', 'password']},
                           _LOGGER):
        return None

    try:
        config['port'] = int(config.get('port', 80))
    except ValueError:
        _LOGGER.error('Invalid port number provided')
        return False

    add_devices([AmcrestCamera(config)])


def parse_lookup(lookup):
    """Parse the results from config lookups."""
    _LOGGER.debug('Parsing results...')
    _LOGGER.debug(lookup)
    results = {}
    for config in lookup.split('\n'):
        if config != '':
            _LOGGER.debug('Looking up config %s', config)
            if '.' in config:
                key = config.split('.')[-1].split('=')[0]
                value = config.split('.')[-1].split('=')[1]
            else:
                key = config.split('=')[0]
                value = config.split('=')[1]

            results[key] = value

    return results


# pylint: disable=too-many-instance-attributes
class AmcrestCamera(Camera):
    """Support for the Amcrest Camera."""

    def __init__(self, config):
        """Setup Amcrest camera object with request session for auth."""
        super(AmcrestCamera, self).__init__()

        self.ip_addr = config.get('ip')
        port = config.get('port')

        self.session = requests.Session()
        self.session.auth = (config.get('username'),
                             config.get('password'))

        self.base_url = 'http://{}:{}/cgi-bin/'.format(
            self.ip_addr, port) + '{}'

    @property
    def name(self):
        """Return the camera title."""
        get = self.session.get(
            self.base_url.format(
                'configManager.cgi?action=getConfig&name=ChannelTitle'
            )
        )

        results = parse_lookup(get.text)
        return results['Name']

    @property
    def brand(self):
        """Return the brand of the camera."""
        get = self.session.get(
            self.base_url.format(
                'magicBox.cgi?action=getVendor'
            )
        )

        results = parse_lookup(get.text)
        return results['vendor']

    @property
    def model(self):
        """Return the model of the camera."""
        get = self.session.get(
            self.base_url.format(
                'magicBox.cgi?action=getDeviceType'
            )
        )

        results = parse_lookup(get.text)
        return results['type']

    @property
    def state_attributes(self):
        """Return the attributes for the state of the camera."""
        attr = {
            'ip': self.ip_addr
        }

        if self.model:
            attr['model_name'] = self.model

        if self.brand:
            attr['brand'] = self.brand

        return attr

    def camera_image(self):
        """Get the current image for the camera."""
        get = self.session.get(
            self.base_url.format(
                'snapshot.cgi?'
            )
        )
        return get.content

    def mjpeg_stream(self, response):
        """Stream the video from the camera."""
        return response(
            self.session.get(
                self.base_url.format('mjpg/video.cgi?'),
                stream=True),
            content_type=('multipart/x-mixed-replace; '
                          'boundary=myboundary')
        )
