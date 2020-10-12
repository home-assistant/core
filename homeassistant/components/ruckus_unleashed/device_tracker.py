"""Support for Ruckus Unleashed devices."""
from homeassistant.components.device_tracker import (
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CLIENTS, COORDINATOR, DOMAIN, UNDO_UPDATE_LISTENERS


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for Ruckus Unleashed component."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    tracked = set()

    @callback
    def router_update():
        """Update the values of the router."""
        add_new_entities(coordinator, async_add_entities, tracked)

    router_update()

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENERS].append(
        coordinator.async_add_listener(router_update)
    )

    registry = await entity_registry.async_get_registry(hass)
    restore_entities(registry, coordinator, entry, async_add_entities, tracked)


@callback
def add_new_entities(coordinator, async_add_entities, tracked):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac in coordinator.data[CLIENTS].keys():
        if mac in tracked:
            continue

        device = coordinator.data[CLIENTS][mac]
        new_tracked.append(RuckusUnleashedDevice(coordinator, mac, device[CONF_NAME]))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked, True)


@callback
def restore_entities(registry, coordinator, entry, async_add_entities, tracked):
    """Restore clients that are not a part of active clients list."""
    missing = []

    for entity in registry.entities.values():
        if entity.config_entry_id == entry.entry_id and entity.platform == DOMAIN:
            if entity.unique_id not in coordinator.data[CLIENTS]:
                missing.append(
                    RuckusUnleashedDevice(
                        coordinator, entity.unique_id, entity.original_name
                    )
                )
                tracked.add(entity.unique_id)

    if missing:
        async_add_entities(missing, True)


class RuckusUnleashedDevice(CoordinatorEntity, ScannerEntity):
    """Representation of a Ruckus Unleashed client."""

    def __init__(self, coordinator, mac, name) -> None:
        """Initialize a Ruckus Unleashed client."""
        super().__init__(coordinator)
        self._mac = mac
        self._name = name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name."""
        if self.is_connected:
            return (
                self.coordinator.data[CLIENTS][self._mac][CONF_NAME]
                or f"Ruckus {self._mac}"
            )
        return self._name

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self.coordinator.data[CLIENTS]

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            ATTR_SOURCE_TYPE: self.source_type,
            ATTR_MAC: self._mac,
        }
