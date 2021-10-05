"""Platform for sensor integration."""
from __future__ import annotations
from typing import Any
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import callback
from .const import DOMAIN
from . import async_create_new_platform_entity
from homeassistant.components import oocsi


async def async_setup_entry(hass, ConfigEntry, async_add_entities, discovery_info=None):
    """Set up the Oocsi number platform."""

    api = hass.data[DOMAIN][ConfigEntry.entry_id]
    platform = "number"
    await async_create_new_platform_entity(
        hass, ConfigEntry, api, BasicNumber, async_add_entities, platform
    )


class BasicNumber(NumberEntity):
    def __init__(self, hass, entity_name, api, entityProperty):
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._oocsichannel = entityProperty["channelName"]

        self._attr_unique_id = entityProperty["channelName"]
        self._attr_max_value = entityProperty["max"]
        self._attr_min_value = entityProperty["min"]
        # self._attr_step = entityProperty["step"]
        self._channelValue = entityProperty["value"]
        self._attr_unit_of_measurement = entityProperty["unit"]

    async def async_added_to_hass(self) -> None:
        @callback
        def channelUpdateEvent(sender, recipient, event):
            """executeOocsi state change."""
            self._channelValue = event["value"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channelUpdateEvent)

    @property
    def device_info(self):
        """Return name."""
        return {"name": self._name}

    # @property
    # def icon(self) -> str:

    #     return self._icon

    @property
    def value(self):
        """Return value."""
        return self._channelValue

    async def async_set_value(self, value: float):
        self._channelValue = value
        self._oocsi.send(self._oocsichannel, {"value": self._channelValue})
