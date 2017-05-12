"""Provide a mock image processing."""

from homeassistant.components.image_processing import ImageProcessingEntity


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the test image_processing platform."""
    add_devices([TestImageProcessing('camera.demo_camera', "Test")])


class TestImageProcessing(ImageProcessingEntity):
    """Test image processing entity."""

    def __init__(self, camera_entity, name):
        """Initialize test image processing."""
        self._name = name
        self._camera = camera_entity
        self._count = 0
        self._image = ""

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

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

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {'image': self._image}

    def process_image(self, image):
        """Process image."""
        self._image = image
        self._count += 1
