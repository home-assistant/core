"""HomePilot base entity."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity


class HomePilotEntity(CoordinatorEntity):
    """Parent class for HomePilot entities."""

    def __init__(self, instance, uid):
        """Initialize common aspects of an HomePilot device."""
        super().__init__(instance["coordinator"])
        self.api = instance["api"]
        self.uid = uid

    @property
    def _device(self):
        """Return HomePilot device object."""
        return self.coordinator.data[self.uid]

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._device.uid

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name
