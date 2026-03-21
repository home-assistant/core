"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SourceType,
    TrackerEntity,
)
from homeassistant.components.device_tracker.legacy import AsyncSeeCallback
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
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

    Follows the same pattern as freebox and unifi: entities are added via
    async_add_entities. Disabled entities do not create devices; devices
    are created only when the user enables the entity.
    """
    coordinator = entry.runtime_data
    ent_reg = er.async_get(hass)

    # 1. Identify all MACs we already know about from the registry for this entry.
    # This ensures they show up as 'not_home' instead of disappearing if missing
    # from the current poll.
    registry_entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    initial_macs = {e.unique_id for e in registry_entries if e.unique_id}

    # 1.5 Get host device for via_device linking (ensures host device exists)
    dr_reg = dr.async_get(hass)
    dr_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})

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
        async_add_entities(
            SnmpTrackerEntity(coordinator, entry, mac) for mac in initial_macs
        )

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
                    SnmpTrackerEntity(coordinator, entry, mac, default_enabled)
                )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpUpdateCoordinator], TrackerEntity):
    """Represent an individual device tracked via SNMP."""

    _attr_should_poll = False
    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        coordinator: SnmpUpdateCoordinator,
        entry: SnmpConfigEntry,
        mac: str,
        default_enabled: bool = False,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._attr_entity_registry_enabled_default = default_enabled
        self._entry = entry

    @property
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self.is_connected:
            return STATE_HOME
        return STATE_NOT_HOME

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        return self._attr_entity_registry_enabled_default

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity (just the MAC address)."""
        assert self._attr_mac_address is not None
        return self._attr_mac_address

    @property
    def name(self) -> str:
        """Return the name of the device (IP or MAC address with underscores)."""
        if (
            self.coordinator.data
            and self._attr_mac_address is not None
            and (ip := self.coordinator.data.get(self._attr_mac_address))
        ):
            return ip

        assert self._attr_mac_address is not None
        return self._attr_mac_address.replace(":", "_")

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device value for this entity."""
        name = self.name
        assert self._attr_mac_address is not None
        return dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._attr_mac_address)},
            via_device=(DOMAIN, self._entry.entry_id),
            name=name,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes of the device."""
        attributes: dict[str, Any] = {}

        if (
            self.coordinator.data
            and self._attr_mac_address is not None
            and (ip := self.coordinator.data.get(self._attr_mac_address))
        ):
            attributes["ip"] = ip

        latitude = getattr(self.hass.config, "latitude", None)
        longitude = getattr(self.hass.config, "longitude", None)
        if latitude is not None:
            attributes["latitude"] = latitude
        if longitude is not None:
            attributes["longitude"] = longitude

        attributes["gps_accuracy"] = 0

        return attributes
