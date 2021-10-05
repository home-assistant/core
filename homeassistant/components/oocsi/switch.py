"""Platform for sensor integration."""
from __future__ import annotations
from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import callback
from .const import DOMAIN
from . import async_create_new_platform_entity


async def async_setup_entry(hass, ConfigEntry, async_add_entities):
    """Set up the Oocsi sensor platform."""

    api = hass.data[DOMAIN][ConfigEntry.entry_id]
    platform = "switch"
    await async_create_new_platform_entity(
        hass, ConfigEntry, api, BasicSwitch, async_add_entities, platform
    )


class BasicSwitch(SwitchEntity):
    def __init__(self, hass, entity_name, api, entityProperty):
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._attr_unique_id = entityProperty["channelName"]
        self._oocsichannel = entityProperty["channelName"]
        self._channelState = False

    async def async_added_to_hass(self) -> None:
        @callback
        def channelUpdateEvent(sender, recipient, event):
            self._channelState = event["state"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channelUpdateEvent)

    @property
    def device_info(self):
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        # return self._static_info.icon
        return "mdi:toggle-switch"

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channelState

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._oocsi.send(self._oocsichannel, {"state": True})
        self._channelState = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._oocsichannel, {"state": False})
        self._channelState = False
