"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import async_create_new_platform_entity
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Oocsi sensor platform."""

    api = hass.data[DOMAIN][config_entry.entry_id]
    platform = "switch"
    await async_create_new_platform_entity(
        hass, config_entry, api, BasicSwitch, async_add_entities, platform
    )


class BasicSwitch(SwitchEntity):
    """Basic oocsi switch."""

    def __init__(self, hass, entity_name, api, entityProperty, device):
        """Set basic oocsi switch parameters."""
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._attr_unique_id = entityProperty["channel_name"]
        self._oocsichannel = entityProperty["channel_name"]
        self._channel_state = False
        self._attr_device_info = {
            "name": entity_name,
            "manufacturer": entityProperty["creator"],
            "via_device_id": device,
        }

        if "logo" in entityProperty:
            self._icon = entityProperty["logo"]
        else:
            self._icon = "mdi:toggle-switch"

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Update state on oocsi update."""
            self._channel_state = event["state"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channel_update_event)

    @property
    def device_info(self):
        """Return important device info."""
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channel_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._oocsi.send(self._oocsichannel, {"state": True})
        self._channel_state = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._oocsichannel, {"state": False})
        self._channel_state = False
