"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from . import async_create_new_platform_entity
from .const import DOMAIN


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Oocsi sensor platform."""

    api = hass.data[DOMAIN][config_entry.entry_id]
    platform = "binary_sensor"
    await async_create_new_platform_entity(
        hass, config_entry, api, BasicSensor, async_add_entities, platform
    )


class BasicSensor(BinarySensorEntity):
    """Basic oocsi binary sensor."""

    def __init__(self, hass, entity_name, api, entityProperty, device):
        """Set basic oocsi binary sensor parameters."""
        self._attr_device_info = {
            "name": entity_name,
            "manufacturer": entityProperty["creator"],
            "via_device_id": device,
        }
        self._hass = hass
        self._oocsi = api
        self._name = entity_name
        self._device_class = entityProperty["type"]
        self._attr_unique_id = entityProperty["channelName"]
        self._oocsichannel = entityProperty["channelName"]
        self._channel_state = False

        if "logo" in entityProperty:
            self._icon = entityProperty["logo"]
        else:
            self._icon = "mdi:electric-switch"

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Execute oocsi state change."""
            self._channel_state = event["state"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channel_update_event)

    @property
    def device_info(self):
        """Return name."""
        return {"name": self._name}

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def icon(self) -> str:
        """Return the icon."""
        # return self._static_info.icon
        return self._icon

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channel_state
