"""Sensor platform for the EnergyID integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntryChange
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnergyIDConfigEntry
from .const import (
    CONF_DEVICE_ID,
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    DATA_CLIENT,
    DOMAIN,
    SIGNAL_CONFIG_ENTRY_CHANGED,
)

_LOGGER = logging.getLogger(__name__)

# Using a coordinator-like pattern for state changes
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the EnergyID status sensor from a config entry."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "EnergyID data not found for entry %s during sensor setup", entry.entry_id
        )
        return

    async_add_entities([EnergyIDStatusSensor(hass, entry)])


class EnergyIDStatusSensor(SensorEntity):
    """Representation of an EnergyID status sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "mappings"
    _attr_name = "Status"
    _attr_icon = "mdi:cloud-sync"

    def __init__(self, hass: HomeAssistant, entry: EnergyIDConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"

        # Associate the sensor with a specific device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_DEVICE_ID])},
            name=entry.title,
            manufacturer="EnergyID",
            model="Webhook Bridge",
            entry_type=DeviceEntryType.SERVICE,
        )

        self._update_attributes()

    @callback
    def _update_attributes(self) -> None:
        """Update sensor state and attributes."""
        entity_count = 0
        is_claimed = None
        last_sync = None
        webhook_url = None
        webhook_policy = None
        mappings = {}

        # Get the WebhookClient from runtime_data
        client = (
            self._entry.runtime_data if hasattr(self._entry, "runtime_data") else None
        )

        # Fallback to domain_data for backward compatibility
        if (
            client is None
            and self.hass.data.get(DOMAIN)
            and (domain_data := self.hass.data[DOMAIN].get(self._entry.entry_id))
        ):
            client = domain_data.get(DATA_CLIENT)

        entity_count = len(self._entry.options)

        if client:
            is_claimed = client.is_claimed
            last_sync = client.last_sync_time
            webhook_url = client.webhook_url
            webhook_policy = client.webhook_policy

        for option_data in self._entry.options.values():
            if isinstance(option_data, dict):
                if (ha_id := option_data.get(CONF_HA_ENTITY_ID)) and (
                    eid_key := option_data.get(CONF_ENERGYID_KEY)
                ):
                    mappings[ha_id] = eid_key
                    _LOGGER.debug("Tracking %s -> %s", ha_id, eid_key)

        self._attr_native_value = entity_count
        last_sync_iso = last_sync.isoformat() if last_sync else None

        self._attr_extra_state_attributes = {
            "claimed": is_claimed,
            "last_sync": last_sync_iso,
            "webhook_endpoint": webhook_url,
            "mapped_entities": mappings,
            "webhook_policy": webhook_policy,
            "config_entry_id": self._entry.entry_id,
        }

    @callback
    def _handle_entry_update(
        self, change_type: ConfigEntryChange, entry: EnergyIDConfigEntry
    ) -> None:
        """Handle updates to the config entry."""
        if entry.entry_id == self._entry.entry_id:
            _LOGGER.debug(
                "Config entry %s updated, refreshing status sensor", entry.entry_id
            )
            self._update_attributes()
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when the entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._handle_entry_update
            )
        )
