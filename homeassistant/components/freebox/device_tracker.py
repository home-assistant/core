"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

from datetime import datetime
from typing import Any

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_DEVICE_NAME, DEVICE_ICONS
from .router import FreeboxConfigEntry, FreeboxRouter


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Freebox component."""
    router = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    @callback
    def remove_stale_entities() -> None:
        """Drop entities for MACs the Freebox no longer reports."""
        entity_registry = er.async_get(hass)
        current_macs = set(router.devices)
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if registry_entry.domain != DEVICE_TRACKER_DOMAIN:
                continue
            stale_mac = dr.format_mac(registry_entry.unique_id)
            if stale_mac not in current_macs:
                entity_registry.async_remove(registry_entry.entity_id)
                tracked.discard(stale_mac)

    entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, router.signal_device_update, remove_stale_entities
        )
    )

    update_router()
    remove_stale_entities()


@callback
def add_entities(
    router: FreeboxRouter,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(FreeboxDevice(router, device))
        tracked.add(mac)

    async_add_entities(new_tracked, True)


class FreeboxDevice(ScannerEntity):
    """Representation of a Freebox device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, router: FreeboxRouter, device: dict[str, Any]) -> None:
        """Initialize a Freebox device."""
        self._router = router
        self._name = device["primary_name"].strip() or DEFAULT_DEVICE_NAME
        self._mac = dr.format_mac(device["l2ident"]["id"])
        self._manufacturer = device["vendor_name"]
        self._attr_icon = icon_for_freebox_device(device)
        self._active = False
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox device."""
        # The router prunes stale devices on each scan; if this entity's MAC
        # was just dropped, skip until the cleanup callback removes us.
        if (device := self._router.devices.get(self._mac)) is None:
            return
        self._active = device["active"]
        if device.get("attrs") is None:
            # device
            self._attr_extra_state_attributes = {
                "last_time_reachable": datetime.fromtimestamp(
                    device["last_time_reachable"]
                ),
                "last_time_activity": datetime.fromtimestamp(device["last_activity"]),
            }
        else:
            # router
            self._attr_extra_state_attributes = device["attrs"]

    @property
    def mac_address(self) -> str:
        """Return a unique ID."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._active

    @callback
    def async_on_demand_update(self) -> None:
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )


def icon_for_freebox_device(device: dict[str, Any]) -> str:
    """Return a device icon from its type."""
    return DEVICE_ICONS.get(device["host_type"], "mdi:help-network")
