"""Sensor platform for the EnergyID integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnergyIDConfigEntry
from .const import CONF_DEVICE_ID, DOMAIN, SIGNAL_CONFIG_ENTRY_CHANGED

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the EnergyID status sensor from a config entry."""
    async_add_entities([EnergyIDStatusSensor(entry)])


class EnergyIDStatusSensor(SensorEntity):
    """Representation of an EnergyID status sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Status"
    _attr_icon = "mdi:cloud-sync"
    _attr_native_unit_of_measurement = "mappings"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_DEVICE_ID])},
            name=entry.title,
            manufacturer="EnergyID",
            model="Webhook Bridge",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        """Return the number of active sensor mappings."""
        return len(self._entry.subentries)

    async def async_added_to_hass(self) -> None:
        """Register callbacks when the entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_CONFIG_ENTRY_CHANGED,
                self._handle_config_update,
            )
        )

    @callback
    def _handle_config_update(self, event_type: str, entry: ConfigEntry) -> None:
        """Handle updates to the config entry options."""
        if entry.entry_id == self._entry.entry_id:
            _LOGGER.debug("Status sensor received config update signal")
            self.async_write_ha_state()
            self.async_write_ha_state()
