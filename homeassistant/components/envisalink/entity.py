"""Support for Envisalink devices."""

from homeassistant.helpers.entity import Entity


class EnvisalinkEntity(Entity):
    """Representation of an Envisalink device."""

    _attr_should_poll = False

    def __init__(self, name, info, controller):
        """Initialize the device."""
        self._controller = controller
        self._info = info
        self._name = name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name
