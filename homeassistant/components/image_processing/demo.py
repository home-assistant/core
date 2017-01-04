"""
Support for the demo image processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/demo/
"""

from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # NOQA
from homeassistant.components.image_processing import ImageProcessingAlprEntity


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the demo light platform."""
    add_devices([DemoImageProcessingAlpr('camera.demo_camera', "Demo Alpr")])


class DemoImageProcessingAlpr(ImageProcessingAlprEntity):
    """Demo alpr image processing entity."""

    def __init__(self, camera_entity, name):
        """Initialize demo alpr."""
        self.name = name
        self.camera_entity = camera_entity

    @property
    def name(self):
        """Return the name of the entity."""
        return self.name

    def image_processing(self, image):
        """Process image."""
        demo_data = {
            'AC3829': 98.3,
            'BE392034': 95.5,
            'CD02394': 93.4,
            'DF923043': 90.8
        }

        self.async_process_plates(demo_data)
