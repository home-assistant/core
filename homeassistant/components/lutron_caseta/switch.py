"""Support for Lutron Caseta switches."""

from typing import Any

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDeviceUpdatableEntity
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta switch platform.

    Adds switches from the Caseta bridge associated with the config_entry as
    switch entities.
    """
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    switch_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(
        LutronCasetaLight(switch_device, data) for switch_device in switch_devices
    )


class LutronCasetaLight(LutronCasetaDeviceUpdatableEntity, SwitchEntity):
    """Representation of a Lutron Caseta switch."""

    def __init__(self, device, data):
        """Init a button entity."""

        super().__init__(device, data)
        self._enabled_default = True

        if "parent_device" not in device:
            return

        keypads = data.keypad_data.keypads
        parent_keypad = keypads[device["parent_device"]]
        parent_device_info = parent_keypad["device_info"]
        # Append the child device name to the end of the parent keypad name to create the entity name
        self._attr_name = f'{parent_device_info["name"]} {device["device_name"]}'
        # Set the device_info to the same as the Parent Keypad
        # The entities will be nested inside the keypad device
        self._attr_device_info = parent_device_info

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._smartbridge.turn_on(self.device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._smartbridge.turn_off(self.device_id)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device["current_state"] > 0
