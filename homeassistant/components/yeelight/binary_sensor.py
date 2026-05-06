"""Sensor platform support for yeelight."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YeelightConfigEntry
from .const import DATA_UPDATED
from .entity import YeelightEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YeelightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yeelight from a config entry."""
    device = config_entry.runtime_data
    if device.is_nightlight_supported:
        _LOGGER.debug("Adding nightlight mode sensor for %s", device.name)
        async_add_entities([YeelightNightlightModeSensor(device, config_entry)])


class YeelightNightlightModeSensor(YeelightEntity, BinarySensorEntity):
    """Representation of a Yeelight nightlight mode sensor."""

    _attr_translation_key = "nightlight"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                DATA_UPDATED.format(self._device.host),
                self.async_write_ha_state,
            )
        )
        await super().async_added_to_hass()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._unique_id}-nightlight_sensor"

    @property
    def is_on(self) -> bool:
        """Return true if nightlight mode is on."""
        return self._device.is_nightlight_enabled
