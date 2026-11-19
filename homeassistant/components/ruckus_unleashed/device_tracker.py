"""Support for Ruckus devices."""

import logging
from typing import override

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import API_CLIENT_HOSTNAME, API_CLIENT_IP, CONF_MAC_FILTER, KEY_SYS_CLIENTS
from .coordinator import RuckusDataUpdateCoordinator, RuckusUnleashedConfigEntry

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RuckusUnleashedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Ruckus component."""
    coordinator = entry.runtime_data

    tracked: set[str] = set()

    mac_filter: set[str] = set(entry.options.get(CONF_MAC_FILTER, []))

    @callback
    def router_update():
        """Update the values of the router."""
        add_new_entities(coordinator, async_add_entities, tracked, mac_filter)

    router_update()

    entry.async_on_unload(coordinator.async_add_listener(router_update))

    restore_entities(
        er.async_get(hass),
        dr.async_get(hass),
        coordinator,
        entry,
        async_add_entities,
        tracked,
        mac_filter,
    )


@callback
def add_new_entities(coordinator, async_add_entities, tracked, mac_filter):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac in coordinator.data[KEY_SYS_CLIENTS]:
        if mac in tracked:
            continue

        if mac_filter and mac not in mac_filter:
            continue

        device = coordinator.data[KEY_SYS_CLIENTS][mac]
        _LOGGER.debug("adding new device: [%s] %s", mac, device[API_CLIENT_HOSTNAME])
        new_tracked.append(RuckusDevice(coordinator, mac, device[API_CLIENT_HOSTNAME]))
        tracked.add(mac)

    async_add_entities(new_tracked)


@callback
def restore_entities(
    registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    coordinator: RuckusDataUpdateCoordinator,
    entry: RuckusUnleashedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
    mac_filter: set[str],
) -> None:
    """Restore clients that are not a part of active clients list."""
    missing: list[RuckusDevice] = []

    for entity in registry.entities.get_entries_for_config_entry_id(entry.entry_id):
        if (
            entity.platform == entry.domain
            and entity.unique_id not in coordinator.data[KEY_SYS_CLIENTS]
            and (not mac_filter or entity.unique_id in mac_filter)
        ):
            # Only set for trackers not added since their device carries the
            # client name, can be removed in HA Core 2027.5
            name = entity.original_name
            if (
                name is None
                and entity.device_id
                and (device := device_registry.async_get(entity.device_id))
            ):
                name = device.name
            missing.append(RuckusDevice(coordinator, entity.unique_id, name))
            tracked.add(entity.unique_id)

    _LOGGER.debug("added %d missing devices", len(missing))
    async_add_entities(missing)


class RuckusDevice(CoordinatorEntity[RuckusDataUpdateCoordinator], ScannerEntity):
    """Representation of a Ruckus client."""

    def __init__(self, coordinator, mac, name: str | None) -> None:
        """Initialize a Ruckus client."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)}, name=name or mac
        )

    @property
    @override
    def mac_address(self) -> str:
        """Return a mac address."""
        return self._mac

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the ip address."""
        if not self.is_connected:
            return None
        return self.coordinator.data[KEY_SYS_CLIENTS][self._mac][API_CLIENT_IP]

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self.coordinator.data[KEY_SYS_CLIENTS]

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Rename the device when the hostname of a connected client changes."""
        if (
            self.is_connected
            and (
                hostname := self.coordinator.data[KEY_SYS_CLIENTS][self._mac][
                    API_CLIENT_HOSTNAME
                ]
            )
            and (device := self.device_entry)
            and device.name != hostname
        ):
            dr.async_get(self.hass).async_update_device(device.id, name=hostname)
        super()._handle_coordinator_update()
