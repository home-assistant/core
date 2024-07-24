"""Platform for switch integration."""

from __future__ import annotations

import logging

from triggercmd import client

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TriggercmdConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TriggercmdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switch for passed config_entry in HA."""
    hub = config_entry.runtime_data
    async_add_entities(TRIGGERcmdSwitch(switch) for switch in hub.switches)


class TRIGGERcmdSwitch(SwitchEntity):
    """Representation of a Switch."""

    _attr_has_entity_name = True
    should_poll = False

    def __init__(self, switch) -> None:
        """Initialize the switch."""
        self._switch = switch
        self._state = False
        self._assumed_state = False
        self._attr_unique_id = f"{self._switch.switch_id}_switch"
        self._attr_name = None

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._switch.switch_id)},
            name=str(self._switch.name).capitalize(),
            sw_version=self._switch.firmware_version,
            model=self._switch.model,
            manufacturer=self._switch.hub.manufacturer,
        )

    @property
    def available(self) -> bool:
        """Return True if hub is available."""
        return self._switch.hub.online

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self._assumed_state = True
        self.async_write_ha_state()
        self.trigger("on")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self._assumed_state = False
        self.async_write_ha_state()
        self.trigger("off")

    def trigger(self, params):
        """Trigger the command."""
        token = self._switch.hub.token

        computer, trigger = self._switch.name.split(" | ")
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
