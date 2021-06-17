"""Integration for Energenie switch."""
from gpiozero import Energenie

from homeassistant.components.switch import DEVICE_CLASS_OUTLET, SwitchEntity
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a config entry."""
    async_add_entities([EnergenieSwitch(hass, config_entry.data)], True)


class EnergenieSwitch(SwitchEntity):
    """Switch that controls Energenie devices using pimote."""

    def __init__(self, hass, config) -> None:
        """Initialize relay switch."""
        self.socket = Energenie(config["socket_number"])
        self._state = STATE_OFF
        self._name = config["name"]

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_OUTLET

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_ASSUMED_STATE: True
        }

    def turn_on(self):
        """Turn the switch on."""
        self.socket.on()
        self._state = STATE_ON

    def turn_off(self):
        """Turn the switch off."""
        self.socket.off()
        self._state = STATE_OFF
