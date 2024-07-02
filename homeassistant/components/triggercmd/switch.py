"""Platform for sensor integration."""

from __future__ import annotations

import logging

from triggercmd import client

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switch for passed config_entry in HA."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(TRIGGERcmdSwitch(switch) for switch in hub.switches)


class TRIGGERcmdSwitch(SwitchEntity):
    """Representation of a Switch."""

    should_poll = False

    def __init__(self, switch) -> None:
        """Initialize the switch."""
        self._switch = switch
        self._name = switch.name
        self._state = False
        self._attr_unique_id = f"{self._switch.switch_id}_switch"

        self._attr_name = self._switch.name

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._switch.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._switch.remove_callback(self.async_write_ha_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._switch.switch_id)},
            "name": str(self.name),
            "sw_version": self._switch.firmware_version,
            "model": self._switch.model,
            "manufacturer": self._switch.hub.manufacturer,
        }

    @property
    def available(self) -> bool:
        """Return True if switch and hub is available."""
        return self._switch.online and self._switch.hub.online

    @property
    def name(self) -> str:
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self.async_write_ha_state()
        self.trigger("on")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self.async_write_ha_state()
        self.trigger("off")

    def trigger(self, params):
        """Trigger the command."""
        token = self._switch.hub.token

        computer, trigger = self.name.split(" | ")
        computer = computer.strip()
        trigger = trigger.strip()
        sender = "Home Assistant"
        data = {
            "computer": computer,
            "trigger": trigger,
            "params": params,
            "sender": sender,
        }
        r = client.trigger(token, data)
        _LOGGER.info("TRIGGERcmd response for %s: %s", self.name, r.json())
