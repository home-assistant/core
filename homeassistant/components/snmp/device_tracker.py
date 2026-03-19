"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import logging
from typing import Any

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
from .const import CONF_IMPORTED_BY, DOMAIN
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
    """Set up the SNMP device tracker from a Config Entry."""
    coordinator = entry.runtime_data
    ent_reg = er.async_get(hass)

    # 1. Identity all MACs we already know about from the registry for this entry.
    # This ensures they show up as 'not_home' instead of 'not provided' if missing from the current poll.
    registry_entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    initial_macs = {e.unique_id for e in registry_entries if e.unique_id}

    # 2. Pre-cleanup: Remove legacy or restored states that conflict with our registered entities.
    # We do this before adding our own entities to ensure their entity_ids are available.
    for reg_entry in registry_entries:
        if hass.states.get(reg_entry.entity_id):
            _LOGGER.debug(
                "Removing existing state %s to avoid conflicts during setup",
                reg_entry.entity_id,
            )
            hass.states.async_remove(reg_entry.entity_id)

    # 3. Add entities for all known MACs immediately
    if initial_macs:
        async_add_entities(
            [SnmpTrackerEntity(coordinator, entry, mac) for mac in initial_macs]
        )

    tracked_macs = set(initial_macs)

    @callback
    def _handle_coordinator_update() -> None:
        """Handle updated data from the coordinator."""
        new_entities = []
        if coordinator.data:
            for mac in coordinator.data:
                if mac not in tracked_macs:
                    # discovery of a brand new device
                    entity_slug = mac.replace(":", "_").lower()
                    legacy_id = f"{DEVICE_TRACKER_DOMAIN}.{entity_slug}"
                    if not ent_reg.async_get(legacy_id) and hass.states.get(legacy_id):
                        hass.states.async_remove(legacy_id)

                    tracked_macs.add(mac)
                    new_entities.append(SnmpTrackerEntity(coordinator, entry, mac))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpUpdateCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP."""

    _attr_should_poll = False

    def __init__(
        self, coordinator: SnmpUpdateCoordinator, entry: SnmpConfigEntry, mac: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._entry = entry

    @property
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity (just the MAC address)."""
        assert self._attr_mac_address is not None
        return self._attr_mac_address

    @property
    def name(self) -> str:
        """Return the name of the device (MAC address with underscores)."""
        assert self._attr_mac_address is not None
        return self._attr_mac_address.replace(":", "_")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default.

        Entities are enabled by default if they were imported from YAML configuration,
        to avoid breaking existing automations.
        """
        return CONF_IMPORTED_BY in self._entry.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes of the device."""
        attributes: dict[str, Any] = {}

        latitude = getattr(self.hass.config, "latitude", None)
        longitude = getattr(self.hass.config, "longitude", None)
        if latitude is not None:
            attributes["latitude"] = latitude
        if longitude is not None:
            attributes["longitude"] = longitude

        attributes["gps_accuracy"] = 0

        return attributes
