"""Support for monitoring juicenet/juicepoint/juicebox based EVSE switches."""
import logging

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN

from .entity import JuiceNetDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entities = []
    for device in hass.data[DOMAIN][config_entry.entry_id].devices:
        entities.append(JuiceNetChargeNowSwitch(device, hass))
    async_add_entities(entities)


class JuiceNetChargeNowSwitch(JuiceNetDevice, SwitchEntity):
    """Implementation of a JuiceNet switch."""

    def __init__(self, device, hass):
        """Initialise the switch."""
        super().__init__(device, "charge_now", hass)

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self.device.name()} Charge Now"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.getOverrideTime() != 0

    def turn_on(self, **kwargs):
        """Charge now."""
        self.device.setOverride(True)

    def turn_off(self, **kwargs):
        """Don't charge now."""
        self.device.setOverride(False)
