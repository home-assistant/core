"""Integration for Energenie switch."""
from gpiozero import Energenie

from homeassistant.components.switch import DEVICE_CLASS_OUTLET, SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a config entry."""
    async_add_entities([EnergenieSwitch(hass, config_entry.data)], True)


class EnergenieSwitch(SwitchEntity):
    """Switch that controls Energenie devices using pimote."""
    _attr_assumed_state: bool = True
    _attr_device_class = DEVICE_CLASS_OUTLET

    def __init__(self, hass, config) -> None:
        """Initialize relay switch."""
        self.socket = Energenie(config["socket_number"])
        self._state = STATE_OFF
        self._name = config["name"]

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return True if self._state == STATE_ON else False

    def turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        self.socket.on()
        self._state = STATE_ON

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        self.socket.off()
        self._state = STATE_OFF
