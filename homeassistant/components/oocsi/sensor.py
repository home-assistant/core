"""Platform for sensor integration."""
from __future__ import annotations
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import callback
from .const import DOMAIN
from . import async_create_new_platform_entity


async def async_setup_entry(hass, ConfigEntry, async_add_entities, discovery_info=None):
    """Set up the Oocsi sensor platform."""

    api = hass.data[DOMAIN][ConfigEntry.entry_id]
    platform = "sensor"
    await async_create_new_platform_entity(
        hass, ConfigEntry, api, BasicSensor, async_add_entities, platform
    )


class BasicSensor(SensorEntity):
    def __init__(self, hass, entity_name, api, entityProperty):
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._device_class = entityProperty["type"]
        self._attr_unique_id = entityProperty["channelName"]
        self._oocsichannel = entityProperty["channelName"]
        self._nativeUnit = entityProperty["unit"]
        self._channelState = entityProperty["state"]

    async def async_added_to_hass(self) -> None:
        @callback
        def channelUpdateEvent(sender, recipient, event):
            """executeOocsi state change."""
            self._channelState = event["state"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channelUpdateEvent)

    @property
    def device_class(self) -> str:
        """Return the unit of measurement."""
        return self._device_class

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._nativeUnit

    @property
    def device_info(self):
        """Return name."""
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:sensor"

    @property
    def state(self):
        """Return true if the switch is on."""
        return self._channelState
