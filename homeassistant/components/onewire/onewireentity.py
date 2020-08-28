"""Support for 1-Wire environment sensors."""
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class OneWireEntity(Entity):
    """Implementation of a 1-Wire Entity."""

    def __init__(
        self, device_id, device_file, device_type, entity_type, proxy, initial_value
    ):
        """Initialize the entity."""
        self._parent_device_id = device_id
        self._parent_device_name = proxy.get_device_name(device_id)
        self._parent_device_type = device_type
        self._name = f"{self._parent_device_name} {entity_type.capitalize()}"
        self._device_file = device_file
        self._value_raw = initial_value
        self._proxy = proxy
        self._state = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the entity."""
        return {"device_file": self._device_file, "raw_value": self._value_raw}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device_file

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self._parent_device_id is None:
            return None

        return {
            "identifiers": {(DOMAIN, self._parent_device_id)},
            "manufacturer": "Maxim Integrated",
            "model": self._parent_device_type,
            "name": self._parent_device_name,
        }

    def read_value(self):
        """Read the value from the path."""
        return self._proxy.read_value(self._device_file)

    def write_value(self, value):
        """Write the value to the path."""
        self._proxy.write_value(self._device_file, value)
