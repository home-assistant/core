"""Support for Tesla charger switches."""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import STATE_OFF, STATE_ON

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    controller = hass.data[TESLA_DOMAIN][config_entry.entry_id]["controller"]
    entities = []
    for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"]["switch"]:
        if device.type == "charger switch":
            entities.append(ChargerSwitch(device, controller, config_entry))
            entities.append(UpdateSwitch(device, controller, config_entry))
        elif device.type == "maxrange switch":
            entities.append(RangeSwitch(device, controller, config_entry))
    async_add_entities(entities, True)


class ChargerSwitch(TeslaDevice, SwitchDevice):
    """Representation of a Tesla charger switch."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialise of the switch."""
        self._state = None
        super().__init__(tesla_device, controller, config_entry)

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable charging: %s", self._name)
        await self.tesla_device.start_charge()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable charging for: %s", self._name)
        await self.tesla_device.stop_charge()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return self._state == STATE_ON

    async def async_update(self):
        """Update the state of the switch."""
        _LOGGER.debug("Updating state for: %s", self._name)
        await super().async_update()
        self._state = STATE_ON if self.tesla_device.is_charging() else STATE_OFF


class RangeSwitch(TeslaDevice, SwitchDevice):
    """Representation of a Tesla max range charging switch."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialise the switch."""
        self._state = None
        super().__init__(tesla_device, controller, config_entry)

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable max range charging: %s", self._name)
        await self.tesla_device.set_max()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable max range charging: %s", self._name)
        await self.tesla_device.set_standard()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return self._state

    async def async_update(self):
        """Update the state of the switch."""
        _LOGGER.debug("Updating state for: %s", self._name)
        await super().async_update()
        self._state = bool(self.tesla_device.is_maxrange())


class UpdateSwitch(TeslaDevice, SwitchDevice):
    """Representation of a Tesla update switch."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialise the switch."""
        self._state = None
        tesla_device.type = "update switch"
        super().__init__(tesla_device, controller, config_entry)
        self._name = self._name.replace("charger", "update")
        self.tesla_id = self.tesla_id.replace("charger", "update")

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable updates: %s %s", self._name, self.tesla_device.id())
        self.controller.set_updates(self.tesla_device.id(), True)

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable updates: %s %s", self._name, self.tesla_device.id())
        self.controller.set_updates(self.tesla_device.id(), False)

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return self._state

    async def async_update(self):
        """Update the state of the switch."""
        car_id = self.tesla_device.id()
        _LOGGER.debug("Updating state for: %s %s", self._name, car_id)
        await super().async_update()
        self._state = bool(self.controller.get_updates(car_id))
