"""Sensor platform support for yeelight."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_CONFIG_ENTRIES, DATA_DEVICE, DATA_UPDATED, DOMAIN, YeelightEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Yeelight from a config entry."""
    device = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][config_entry.entry_id][DATA_DEVICE]
    if device.is_nightlight_supported:
        _LOGGER.debug("Adding nightlight mode sensor for %s", device.name)
        async_add_entities([YeelightNightlightModeSensor(device, config_entry)])


class YeelightNightlightModeSensor(YeelightEntity, BinarySensorEntity):
    """Representation of a Yeelight nightlight mode sensor."""

    async def async_added_to_hass(self):
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
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device.name} nightlight"

    @property
    def is_on(self):
        """Return true if nightlight mode is on."""
        return self._device.is_nightlight_enabled
