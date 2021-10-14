"""Support for Abode Security System switches."""
from abodepy.devices.switch import AbodeSwitch as AbodeSW
import abodepy.helpers.constants as CONST

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

    entities = []

    for device_type in DEVICE_TYPES:
        for device in data.abode.get_devices(generic_type=device_type):
            entities.append(AbodeSwitch(data, device))

    for automation in data.abode.get_automations():
        entities.append(AbodeAutomationSwitch(data, automation))  # type: ignore

    async_add_entities(entities)


class AbodeSwitch(AbodeDevice, SwitchEntity):
    """Representation of an Abode switch."""

    _device: AbodeSW

    def turn_on(self, **kwargs) -> None:
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs) -> None:
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.is_on


class AbodeAutomationSwitch(AbodeAutomation, SwitchEntity):
    """A switch implementation for Abode automations."""

    _attr_icon = ICON

    async def async_added_to_hass(self) -> None:
        """Set up trigger automation service."""
        await super().async_added_to_hass()

        signal = f"abode_trigger_automation_{self.entity_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self.trigger))

    def turn_on(self, **kwargs) -> None:
        """Enable the automation."""
        if self._automation.enable(True):
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Disable the automation."""
        if self._automation.enable(False):
            self.schedule_update_ha_state()

    def trigger(self) -> None:
        """Trigger the automation."""
        self._automation.trigger()

    @property
    def is_on(self) -> bool:
        """Return True if the automation is enabled."""
        return self._automation.is_enabled
