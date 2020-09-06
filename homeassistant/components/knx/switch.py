"""Support for KNX/IP switches."""
from xknx.devices import Switch as XknxSwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import DATA_KNX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up switch(es) for KNX platform."""
    entities = []
    for device in hass.data[DATA_KNX].xknx.devices:
        if isinstance(device, XknxSwitch):
            entities.append(KNXSwitch(device))
    async_add_entities(entities)


class KNXSwitch(SwitchEntity):
    """Representation of a KNX switch."""

    def __init__(self, device: XknxSwitch):
        """Initialize of KNX switch."""
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
        """Return true if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """Return the polling state. Not needed within KNX."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.device.state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.device.set_off()
