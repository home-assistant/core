"""Support for interface with a Gree climate systems."""
from __future__ import annotations

from homeassistant.components.switch import DEVICE_CLASS_SWITCH, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DISPATCHERS, DOMAIN
from .entity import GreeEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Gree HVAC device from a config entry."""

    @callback
    def init_device(coordinator):
        """Register the device."""
        async_add_entities(
            [
                GreePanelLightSwitchEntity(coordinator),
                GreeQuietModeSwitchEntity(coordinator),
                GreeFreshAirSwitchEntity(coordinator),
                GreeXFanSwitchEntity(coordinator),
            ]
        )

    for coordinator in hass.data[DOMAIN][COORDINATORS]:
        init_device(coordinator)

    hass.data[DOMAIN][DISPATCHERS].append(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class GreePanelLightSwitchEntity(GreeEntity, SwitchEntity):
    """Representation of the front panel light on the device."""

    def __init__(self, coordinator):
        """Initialize the Gree device."""
        super().__init__(coordinator, "Panel Light")

    @property
    def icon(self) -> str | None:
        """Return the icon for the device."""
        return "mdi:lightbulb"

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self) -> bool:
        """Return if the light is turned on."""
        return self.coordinator.device.light

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.coordinator.device.light = True
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.coordinator.device.light = False
        await self.coordinator.push_state_update()
        self.async_write_ha_state()


class GreeQuietModeSwitchEntity(GreeEntity, SwitchEntity):
    """Representation of the quiet mode state of the device."""

    def __init__(self, coordinator):
        """Initialize the Gree device."""
        super().__init__(coordinator, "Quiet")

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.coordinator.device.quiet

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.coordinator.device.quiet = True
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.coordinator.device.quiet = False
        await self.coordinator.push_state_update()
        self.async_write_ha_state()


class GreeFreshAirSwitchEntity(GreeEntity, SwitchEntity):
    """Representation of the fresh air mode state of the device."""

    def __init__(self, coordinator):
        """Initialize the Gree device."""
        super().__init__(coordinator, "Fresh Air")

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.coordinator.device.fresh_air

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.coordinator.device.fresh_air = True
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.coordinator.device.fresh_air = False
        await self.coordinator.push_state_update()
        self.async_write_ha_state()


class GreeXFanSwitchEntity(GreeEntity, SwitchEntity):
    """Representation of the extra fan mode state of the device."""

    def __init__(self, coordinator):
        """Initialize the Gree device."""
        super().__init__(coordinator, "XFan")

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.coordinator.device.xfan

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.coordinator.device.xfan = True
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.coordinator.device.xfan = False
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
