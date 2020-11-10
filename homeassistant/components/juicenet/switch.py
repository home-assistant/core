"""Support for monitoring juicenet/juicepoint/juicebox based EVSE switches."""
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, JUICENET_API, JUICENET_COORDINATOR
from .entity import JuiceNetDevice


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the JuiceNet switches."""
    entities = []
    juicenet_data = hass.data[DOMAIN][config_entry.entry_id]
    api = juicenet_data[JUICENET_API]
    coordinator = juicenet_data[JUICENET_COORDINATOR]

    for device in api.devices:
        entities.append(JuiceNetChargeNowSwitch(device, coordinator))
    async_add_entities(entities)


class JuiceNetChargeNowSwitch(JuiceNetDevice, SwitchEntity):
    """Implementation of a JuiceNet switch."""

    def __init__(self, device, coordinator):
        """Initialise the switch."""
        super().__init__(device, "charge_now", coordinator)

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self.device.name} Charge Now"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.override_time != 0

    async def async_turn_on(self, **kwargs):
        """Charge now."""
        await self.device.set_override(True)

    async def async_turn_off(self, **kwargs):
        """Don't charge now."""
        await self.device.set_override(False)
