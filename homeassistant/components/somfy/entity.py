"""Entity representing a Somfy device."""

from abc import abstractmethod

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class SomfyEntity(CoordinatorEntity, Entity):
    """Representation of a generic Somfy device."""

    def __init__(self, coordinator, device_id):
        """Initialize the Somfy device."""
        super().__init__(coordinator)
        self._id = device_id

    @property
    def device(self):
        """Return data for the device id."""
        return self.coordinator.data[self._id]

    @property
    def unique_id(self) -> str:
        """Return the unique id base on the id returned by Somfy."""
        return self._id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.name

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "model": self.device.type,
            "via_device": (DOMAIN, self.device.parent_id),
            # For the moment, Somfy only returns their own device.
            "manufacturer": "Somfy",
        }

    def has_capability(self, capability: str) -> bool:
        """Test if device has a capability."""
        capabilities = self.device.capabilities
        return bool([c for c in capabilities if c.name == capability])

    def has_state(self, state: str) -> bool:
        """Test if device has a state."""
        states = self.device.states
        return bool([c for c in states if c.name == state])

    @property
    def assumed_state(self) -> bool:
        """Return if the device has an assumed state."""
        return not bool(self.device.states)

    @callback
    def _handle_coordinator_update(self):
        """Process an update from the coordinator."""
        self._create_device()
        super()._handle_coordinator_update()

    @abstractmethod
    def _create_device(self):
        """Update the device with the latest data."""
