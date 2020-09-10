"""Support for KNX/IP sensors."""
from xknx.devices import Sensor as XknxSensor

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import DATA_KNX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensor(s) for KNX platform."""
    entities = []
    for device in hass.data[DATA_KNX].xknx.devices:
        if isinstance(device, XknxSensor):
            entities.append(KNXSensor(device))
    async_add_entities(entities)


class KNXSensor(Entity):
    """Representation of a KNX sensor."""

    def __init__(self, device: XknxSensor):
        """Initialize of a KNX sensor."""
        self.device = device

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self.device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    async def async_update(self):
        """Update the state from KNX."""
        await self.device.sync()

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.resolve_state()

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self.device.unit_of_measurement()

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self.device.ha_device_class()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return None
