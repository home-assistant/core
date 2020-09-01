"""Support for KNX/IP binary sensors."""
from xknx.devices import BinarySensor as XknxBinarySensor

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from . import DATA_KNX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up binary sensor(s) for KNX platform."""
    entities = []
    for device in hass.data[DATA_KNX].xknx.devices:
        if isinstance(device, XknxBinarySensor):
            entities.append(KNXBinarySensor(device))
    async_add_entities(entities)


class KNXBinarySensor(BinarySensorEntity):
    """Representation of a KNX binary sensor."""

    def __init__(self, device: XknxBinarySensor):
        """Initialize of KNX binary sensor."""
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
        """Request a state update from KNX bus."""
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
    def device_class(self):
        """Return the class of this sensor."""
        return self.device.device_class

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.device.is_on()
