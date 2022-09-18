"""Support for Abode Security System switches."""
from __future__ import annotations

from typing import Any, cast

from abodepy.devices.switch import CONST, AbodeSwitch as AbodeSW

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbodeAutomation, AbodeDevice, AbodeSystem
from .const import DOMAIN

DEVICE_TYPES = [CONST.TYPE_SWITCH, CONST.TYPE_VALVE]

ICON = "mdi:robot"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Abode switch devices."""
    data: AbodeSystem = hass.data[DOMAIN]

    entities: list[SwitchEntity] = [
        AbodeSwitch(data, device)
        for device_type in DEVICE_TYPES
        for device in data.abode.get_devices(generic_type=device_type)
    ]

    entities.extend(
        AbodeAutomationSwitch(data, automation)
        for automation in data.abode.get_automations()
    )

    async_add_entities(entities)


class AbodeSwitch(AbodeDevice, SwitchEntity):
    """Representation of an Abode switch."""

    _device: AbodeSW

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return cast(bool, self._device.is_on)


class AbodeAutomationSwitch(AbodeAutomation, SwitchEntity):
    """A switch implementation for Abode automations."""

    _attr_icon = ICON

    async def async_added_to_hass(self) -> None:
        """Set up trigger automation service."""
        await super().async_added_to_hass()

        signal = f"abode_trigger_automation_{self.entity_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self.trigger))

    def turn_on(self, **kwargs: Any) -> None:
        """Enable the automation."""
        if self._automation.enable(True):
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Disable the automation."""
        if self._automation.enable(False):
            self.schedule_update_ha_state()

    def trigger(self) -> None:
        """Trigger the automation."""
        self._automation.trigger()

    @property
    def is_on(self) -> bool:
        """Return True if the automation is enabled."""
        return bool(self._automation.is_enabled)
