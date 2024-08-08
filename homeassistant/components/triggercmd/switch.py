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
    async_add_entities(TRIGGERcmdSwitch(trigger) for trigger in hub.triggers)


class TRIGGERcmdSwitch(SwitchEntity):
    """Representation of a Switch."""

    _attr_has_entity_name = True
    _attr_assumed_state = True
    should_poll = False

    def __init__(self, trigger) -> None:
        """Initialize the switch."""
        self._switch = trigger
        self._state = False
        self._assumed_state = False
        self._attr_unique_id = f"{self._switch.computer_id}.{self._switch.trigger_id}"
        self._attr_name = self._switch.trigger_id

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._switch.computer_id)},
            name=str(self._switch.computer_id).capitalize(),
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
        self.async_write_ha_state()
        self.trigger("on")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self.async_write_ha_state()
        self.trigger("off")

    def trigger(self, params):
        """Trigger the command."""
        r = client.trigger(
            self._switch.hub.token,
            {
                "computer": self._switch.computer_id,
                "trigger": self._switch.trigger_id,
                "params": params,
                "sender": "Home Assistant",
            },
        )
        _LOGGER.info("TRIGGERcmd trigger response: %s", r.json())
