"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback

from . import async_create_new_platform_entity
from .const import DOMAIN


async def async_setup_entry(hass, ConfigEntry, async_add_entities, discovery_info=None):
    """Set up the Oocsi number platform."""

    api = hass.data[DOMAIN][ConfigEntry.entry_id]
    platform = "number"
    await async_create_new_platform_entity(
        hass, ConfigEntry, api, BasicNumber, async_add_entities, platform
    )


class BasicNumber(NumberEntity):
    """Basic oocsi number input"""

    def __init__(self, hass, entity_name, api, entityProperty, device):
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._oocsichannel = entityProperty["channelName"]
        self._attr_device_info = {
            "name": entity_name,
            "manufacturer": entityProperty["creator"],
            "via_device_id": device,
        }

        self._attr_unique_id = entityProperty["channelName"]
        self._attr_max_value = entityProperty["max"]
        self._attr_min_value = entityProperty["min"]
        # self._attr_step = entityProperty["step"]
        self._channel_value = entityProperty["value"]
        self._attr_unit_of_measurement = entityProperty["unit"]

    async def async_added_to_hass(self) -> None:
        @callback
        def channel_update_event(sender, recipient, event):
            """execute Oocsi state change."""
            self._channel_value = event["value"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channel_update_event)

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
        return self._channel_value

    async def async_set_value(self, value: float):
        self._channel_value = value
        self._oocsi.send(self._oocsichannel, {"value": self._channel_value})
