"""Sensor platform support for yeelight."""
import logging
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISCOVERY, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DATA_CONFIG_ENTRIES,
    DATA_DEVICES,
    DATA_REMOVE_BINARY_SENSOR_DISPATCHER,
    DATA_UPDATED,
    DOMAIN,
    SIGNAL_SETUP_BINARY_SENSOR,
    YeelightEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Yeelight from a config entry."""

    async def async_setup_binary_sensor(ipaddr):
        device = hass.data[DOMAIN][DATA_DEVICES][ipaddr]

        if device.is_nightlight_supported:
            _LOGGER.debug("Adding nightlight mode sensor for %s", device.name)
            async_add_entities([YeelightNightlightModeSensor(device)])

    if config_entry.data[CONF_DISCOVERY]:
        hass.data[DOMAIN][DATA_CONFIG_ENTRIES][config_entry.entry_id][
            DATA_REMOVE_BINARY_SENSOR_DISPATCHER
        ] = async_dispatcher_connect(
            hass, SIGNAL_SETUP_BINARY_SENSOR, async_setup_binary_sensor
        )
    else:
        await async_setup_binary_sensor(config_entry.data[CONF_IP_ADDRESS])


class YeelightNightlightModeSensor(YeelightEntity, BinarySensorEntity):
    """Representation of a Yeelight nightlight mode sensor."""

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                DATA_UPDATED.format(self._device.ipaddr),
                self.async_write_ha_state,
            )
        )

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        unique = self._device.unique_id

        if unique:
            return unique + "-nightlight_sensor"

        return None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device.name} nightlight"

    @property
    def is_on(self):
        """Return true if nightlight mode is on."""
        return self._device.is_nightlight_enabled
