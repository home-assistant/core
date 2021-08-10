"""Support for Tesla charger switches."""
import logging

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    coordinator = hass.data[TESLA_DOMAIN][config_entry.entry_id]["coordinator"]
    entities = []
    for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"]["switch"]:
        if device.type == "charger switch":
            entities.append(ChargerSwitch(device, coordinator))
            entities.append(UpdateSwitch(device, coordinator))
        elif device.type == "maxrange switch":
            entities.append(RangeSwitch(device, coordinator))
        elif device.type == "sentry mode switch":
            entities.append(SentryModeSwitch(device, coordinator))
    async_add_entities(entities, True)


class ChargerSwitch(TeslaDevice, SwitchEntity):
    """Representation of a Tesla charger switch."""

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable charging: %s", self.name)
        await self.tesla_device.start_charge()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable charging for: %s", self.name)
        await self.tesla_device.stop_charge()
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        if self.tesla_device.is_charging() is None:
            return None
        return self.tesla_device.is_charging()


class RangeSwitch(TeslaDevice, SwitchEntity):
    """Representation of a Tesla max range charging switch."""

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable max range charging: %s", self.name)
        await self.tesla_device.set_max()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable max range charging: %s", self.name)
        await self.tesla_device.set_standard()
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        if self.tesla_device.is_maxrange() is None:
            return None
        return bool(self.tesla_device.is_maxrange())


class UpdateSwitch(TeslaDevice, SwitchEntity):
    """Representation of a Tesla update switch."""

    def __init__(self, tesla_device, coordinator):
        """Initialise the switch."""
        super().__init__(tesla_device, coordinator)
        self.controller = coordinator.controller

    @property
    def name(self):
        """Return the name of the device."""
        return super().name.replace("charger", "update")

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return super().unique_id.replace("charger", "update")

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable updates: %s %s", self.name, self.tesla_device.id())
        self.controller.set_updates(self.tesla_device.id(), True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable updates: %s %s", self.name, self.tesla_device.id())
        self.controller.set_updates(self.tesla_device.id(), False)
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        if self.controller.get_updates(self.tesla_device.id()) is None:
            return None
        return bool(self.controller.get_updates(self.tesla_device.id()))


class SentryModeSwitch(TeslaDevice, SwitchEntity):
    """Representation of a Tesla sentry mode switch."""

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable sentry mode: %s", self.name)
        await self.tesla_device.enable_sentry_mode()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable sentry mode: %s", self.name)
        await self.tesla_device.disable_sentry_mode()
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        if self.tesla_device.is_on() is None:
            return None
        return self.tesla_device.is_on()
