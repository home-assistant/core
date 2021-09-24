"""Platform for sensor integration."""
from __future__ import annotations
from homeassistant.components import oocsi
from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from .const import DOMAIN, DATA_OOCSI, DATA_INTERVIEW
from . import _async_interviewer, async_create_new_platform_entity


async def async_setup_entry(hass, ConfigEntry, async_add_entities, discovery_info=None):
    """Set up the Oocsi sensor platform."""
    # if discovery_info is None:
    #     return
    api = hass.data.pop(DATA_OOCSI)

    await async_create_new_platform_entity(hass, ConfigEntry, api, BasicSwitch)


class BasicSwitch(SwitchEntity):
    def __init__(self, device_info, api):
        self._oocsi = api

    @property
    def icon(self) -> str:
        """Return the icon."""
        # return self._static_info.icon
        return

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    # async def _async_listen_to_switch(self):
    # @callback

    # def handleSwitchEvent(sender, recipient, event):
    #     print(event)
    #     if event("state") == True:
    #         print("True")
    #         return True

    #     else:
    #         return False

    # self._oocsi.subscribe("switchChannel", handleSwitchEvent)

    async def is_on(self) -> bool | None:  # type: ignore[override]
        """Return true if the switch is on."""

        # if handleSwitchEvent == True:
        #     return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._oocsi.send("switchChannel", {"state": True})
        print("Set_True")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send("switchChannel", {"state": False})
        # await self._client.switch_command(self._static_info.key, False)
