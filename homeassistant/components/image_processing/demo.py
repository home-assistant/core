"""
Support for the demo image processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/demo/
"""

from homeassistant.components.image_processing import ImageProcessingEntity
from homeassistant.components.image_processing.openalpr_local import (
    ImageProcessingAlprEntity)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the demo image_processing platform."""
    add_devices([
        DemoImageProcessing('camera.demo_camera', "Demo"),
        DemoImageProcessingAlpr('camera.demo_camera', "Demo Alpr")
    ])


class DemoImageProcessing(ImageProcessingEntity):
    """Demo alpr image processing entity."""

    def __init__(self, camera_entity, name):
        """Initialize demo alpr."""
        self._name = name
        self._camera = camera_entity
        self._count = 0

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._count

    def process_image(self, image):
        """Process image."""
        self._count += 1


class DemoImageProcessingAlpr(ImageProcessingAlprEntity):
    """Demo alpr image processing entity."""

    def __init__(self, camera_entity, name):
        """Initialize demo alpr."""
        super().__init__()

        self._name = name
        self._camera = camera_entity

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return 80

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def process_image(self, image):
        """Process image."""
        demo_data = {
            'AC3829': 98.3,
            'BE392034': 95.5,
            'CD02394': 93.4,
            'DF923043': 90.8
        }

        self.process_plates(demo_data, 1)
