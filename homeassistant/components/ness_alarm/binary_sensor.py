"""Support for Ness zone binary sensors."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SIGNAL_ZONE_CHANGED
from .const import DEFAULT_MAX_SUPPORTED_ZONES, DOMAIN, PANEL_MODEL_ZONES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ness zone binary sensors from a config entry."""

    entity_registry = er.async_get(hass)

    panel_model = config_entry.data.get("panel_model", "UNKNOWN")

    if panel_model.startswith("MANUAL_"):
        try:
            zone_str = panel_model.split("_")[1]
            enabled_zones = int(zone_str)
        except (IndexError, ValueError):
            _LOGGER.warning(
                "Invalid manual model format '%s', defaulting to %s zones",
                panel_model,
                DEFAULT_MAX_SUPPORTED_ZONES,
            )
    elif panel_model in PANEL_MODEL_ZONES:
        enabled_zones = PANEL_MODEL_ZONES[panel_model]
    else:
        enabled_zones = DEFAULT_MAX_SUPPORTED_ZONES
        _LOGGER.warning(
            "Unknown panel model '%s', defaulting to %s zones",
            panel_model,
            enabled_zones,
        )

    entities = []

    # Always create 32 zones, and disable based on the number of supported zones from
    for zone_id in range(1, DEFAULT_MAX_SUPPORTED_ZONES + 1):
        name = f"Zone {zone_id}"
        zone_type = BinarySensorDeviceClass.MOTION

        should_be_enabled = zone_id <= enabled_zones

        unique_id = f"{config_entry.entry_id}_zone_{zone_id}"
        existing_entity = entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, unique_id
        )

        if existing_entity:
            current_entry = entity_registry.entities.get(existing_entity)
            if current_entry:
                is_currently_disabled = current_entry.disabled_by is not None

                if should_be_enabled and is_currently_disabled:
                    entity_registry.async_update_entity(
                        existing_entity, disabled_by=None
                    )
                elif not should_be_enabled and not is_currently_disabled:
                    entity_registry.async_update_entity(
                        existing_entity,
                        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                    )

        entities.append(
            NessZoneSensor(
                zone_id,
                name,
                zone_type,
                config_entry.entry_id,
                should_be_enabled,
            )
        )

    async_add_entities(entities)


class NessZoneSensor(BinarySensorEntity):
    """Representation of a Ness zone sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        zone_id: int,
        name: str,
        zone_type: str,
        entry_id: str,
        enabled_by_default: bool,
    ) -> None:
        """Initialize the zone sensor."""
        self._zone_id = zone_id
        self._attr_name = name
        self._attr_device_class = cast(BinarySensorDeviceClass, zone_type)
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_zone_{zone_id}"
        self._state = False

        # Set entity as disabled if beyond panel's capacity
        # This only applies on first creation, not on reload
        self._attr_entity_registry_enabled_default = enabled_by_default

    async def async_added_to_hass(self) -> None:
        """Register callbacks and restore state."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ZONE_CHANGED,
                self._handle_zone_change,
            )
        )

    @callback
    def _handle_zone_change(self, zone_id: int, state: bool) -> None:
        """Handle zone state changes."""
        if zone_id != self._zone_id:
            return

        self._state = state
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return {
            "zone_id": self._zone_id,
        }
