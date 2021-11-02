"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from . import async_create_new_platform_entity
from .const import DOMAIN


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Oocsi sensor platform."""

    api = hass.data[DOMAIN][config_entry.entry_id]
    platform = "sensor"
    await async_create_new_platform_entity(
        hass, config_entry, api, BasicSensor, async_add_entities, platform
    )


class BasicSensor(SensorEntity):
    """Basic oocsi sensor."""

    def __init__(self, hass, entity_name, api, entityProperty, device):
        """Set basic oocsi sensor parameters."""
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._device_class = entityProperty["sensor_type"]
        self._attr_unique_id = entityProperty["channel_name"]
        self._oocsichannel = entityProperty["channel_name"]
        self._native_unit = entityProperty["unit"]
        self._channel_value = entityProperty["value"]
        self._attr_device_info = {
            "name": entity_name,
            "manufacturer": entityProperty["creator"],
            "via_device_id": device,
        }

        if "logo" in entityProperty:
            self._icon = entityProperty["logo"]
        else:
            self._icon = "mdi:flask"

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Execute Oocsi state change."""
            self._channel_value = event["value"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channel_update_event)

    @property
    def device_class(self) -> str:
        """Return the unit of measurement."""
        return self._device_class

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._native_unit

    @property
    def device_info(self):
        """Return name."""
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def state(self):
        """Return true if the switch is on."""
        return self._channel_value
