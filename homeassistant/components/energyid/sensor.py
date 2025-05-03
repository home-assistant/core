"""Sensor platform for the EnergyID integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from energyid_webhooks.client_v2 import WebhookClient

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEVICE_ID,
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    DATA_CLIENT,
    DOMAIN,
    SIGNAL_CONFIG_ENTRY_CHANGED,
)

if TYPE_CHECKING:
    from homeassistant.helpers.dispatcher import ConfigEntryChange

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the EnergyID status sensor from a config entry."""
    # No change needed here, setup remains the same
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "EnergyID data not found for entry %s during sensor setup", entry.entry_id
        )
        return

    async_add_entities([EnergyIDStatusSensor(hass, entry)])


class EnergyIDStatusSensor(SensorEntity):
    """Representation of an EnergyID status sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = (
        True  # Keep True: Name is specific to this status, not device name prefixed
    )
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "mappings"

    # --- Added Attributes ---
    _attr_name = "Status"  # Explicit, static name for this sensor type
    _attr_icon = "mdi:cloud-sync"  # An icon representing cloud sync status

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        # Unique ID remains the same, ensuring entity persistence
        self._attr_unique_id = f"{entry.entry_id}_status"

        # Link to a device associated with this config entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_DEVICE_ID])},
            name=entry.title,  # Device name comes from the config entry title
            manufacturer="EnergyID",
            model="Webhook Bridge",
            entry_type="service",
            # configuration_url="https://app.energyid.eu/..." # Still optional
        )

        # Initial update remains the same
        self._update_attributes()

    @callback
    def _update_attributes(self) -> None:
        """Update sensor state and attributes."""
        # ... (logic for getting count, client status, attributes remains the same) ...
        entity_count = 0
        is_claimed = None
        last_sync = None
        webhook_url = None
        mapped_entities = []
        mapped_keys = []

        if self.hass.data.get(DOMAIN) and (
            domain_data := self.hass.data[DOMAIN].get(self._entry.entry_id)
        ):
            entity_count = len(self._entry.options)
            client: WebhookClient | None = domain_data.get(DATA_CLIENT)
            if client:
                is_claimed = client.is_claimed
                last_sync = client.last_sync_time
                webhook_url = client.webhook_url

            for option_data in self._entry.options.values():
                if isinstance(option_data, dict):
                    if ha_id := option_data.get(CONF_HA_ENTITY_ID):
                        mapped_entities.append(ha_id)
                    if eid_key := option_data.get(CONF_ENERGYID_KEY):
                        mapped_keys.append(eid_key)

        self._attr_native_value = entity_count
        # Ensure last_sync is formatted nicely or None for attributes
        last_sync_iso = last_sync.isoformat() if last_sync else None

        self._attr_extra_state_attributes = {
            "claimed": is_claimed,
            "last_sync": last_sync_iso,  # Keep ISO for machine readability if needed
            "webhook_endpoint": webhook_url,
            "mapped_entities": sorted(mapped_entities),
            "target_energyid_keys": sorted(mapped_keys),
            "config_entry_id": self._entry.entry_id,
        }

    # ... (async_added_to_hass and _handle_entry_update remain the same) ...
    @callback
    def _handle_entry_update(
        self, change_type: ConfigEntryChange, entry: ConfigEntry
    ) -> None:
        """Handle config entry update signal."""
        if entry.entry_id == self._entry.entry_id:
            _LOGGER.debug(
                "Config entry %s updated, refreshing status sensor", entry.entry_id
            )
            self._update_attributes()
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._handle_entry_update
            )
        )
