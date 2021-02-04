"""Support for Velbus sensors."""
from homeassistant.const import DEVICE_CLASS_POWER, ENERGY_KILO_WATT_HOUR

from . import VelbusEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus sensor based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    modules_data = hass.data[DOMAIN][entry.entry_id]["sensor"]
    entities = []
    for address, channel in modules_data:
        module = cntrl.get_module(address)
        entities.append(VelbusSensor(module, channel))
        if module.get_class(channel) == "counter":
            entities.append(VelbusSensor(module, channel, True))
    async_add_entities(entities)


class VelbusSensor(VelbusEntity):
    """Representation of a sensor."""

    def __init__(self, module, channel, counter=False):
        """Initialize a sensor Velbus entity."""
        super().__init__(module, channel)
        self._is_counter = counter

    @property
    def unique_id(self):
        """Return unique ID for counter sensors."""
        unique_id = super().unique_id
        if self._is_counter:
            unique_id = f"{unique_id}-counter"
        return unique_id

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._module.get_class(self._channel) == "counter" and not self._is_counter:
            if self._module.get_counter_unit(self._channel) == ENERGY_KILO_WATT_HOUR:
                return DEVICE_CLASS_POWER
            return None
        return self._module.get_class(self._channel)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._is_counter:
            return self._module.get_counter_state(self._channel)
        return self._module.get_state(self._channel)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        if self._is_counter:
            return self._module.get_counter_unit(self._channel)
        return self._module.get_unit(self._channel)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._is_counter:
            return "mdi:counter"
        return None
