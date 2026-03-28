"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.components.device_tracker.legacy import AsyncSeeCallback
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SnmpConfigEntry
from .const import DOMAIN
from .coordinator import SnmpUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Trigger an import flow to migrate YAML config to a config entry."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnmpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SNMP device tracker from a Config Entry.

    Follows the same pattern as other router integrations: entities are added via
    async_add_entities. ScannerEntity handles the state and attributes.
    """
    coordinator = entry.runtime_data
    ent_reg = er.async_get(hass)

    # 1. Identify all MACs we already know about from the registry for this entry.
    # This ensures they show up as 'not_home' instead of disappearing if missing
    # from the current poll.
    registry_entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    initial_macs = {e.unique_id for e in registry_entries if e.unique_id}

    # 2. Pre-cleanup: Remove legacy or restored states that conflict with our
    # registered entities so their entity_ids are available.
    for reg_entry in registry_entries:
        if hass.states.get(reg_entry.entity_id):
            _LOGGER.debug(
                "Removing existing state %s to avoid conflicts during setup",
                reg_entry.entity_id,
            )
            hass.states.async_remove(reg_entry.entity_id)

    # 3. Add entities for all known MACs immediately
    if initial_macs:
        async_add_entities(SnmpTrackerEntity(coordinator, mac) for mac in initial_macs)

    tracked_macs = set(initial_macs)

    @callback
    def _handle_coordinator_update() -> None:
        """Handle updated data from the coordinator."""
        if not coordinator.data:
            return

        new_entities = []
        for mac in coordinator.data:
            # Discovery of a brand new device.
            if mac not in tracked_macs:
                # 1. Determine if the entity should be enabled by default
                entity_slug = mac.replace(":", "_").lower()
                legacy_id = f"{DEVICE_TRACKER_DOMAIN}.{entity_slug}"
                default_enabled = False
                if not ent_reg.async_get(legacy_id) and hass.states.get(legacy_id):
                    hass.states.async_remove(legacy_id)
                    default_enabled = True

                tracked_macs.add(mac)
                new_entities.append(
                    SnmpTrackerEntity(coordinator, mac, default_enabled)
                )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpUpdateCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SnmpUpdateCoordinator,
        mac: str,
        default_enabled: bool = False,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._attr_entity_registry_enabled_default = default_enabled
        self._attr_unique_id = mac
        self._attr_name = mac.replace(":", "_")
        self._attr_ip_address = coordinator.data.get(mac) if coordinator.data else None
        self._attr_translation_key = "device_tracker"

    @property
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attribute so base class can use it."""
        assert self._attr_mac_address is not None
        self._attr_ip_address = (
            self.coordinator.data.get(self._attr_mac_address)
            if self.coordinator.data
            else None
        )
        super()._handle_coordinator_update()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        return (
            self._attr_entity_registry_enabled_default
            or super().entity_registry_enabled_default
        )
