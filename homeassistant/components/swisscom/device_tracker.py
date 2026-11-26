"""Device tracker for the Swisscom Internet-Box."""

from typing import TYPE_CHECKING, override

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwisscomConfigEntry, SwisscomDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwisscomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker entities for the Swisscom Internet-Box."""
    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    # Formatted MAC address of each tracked client, by client key
    tracked: dict[str, str] = {}

    @callback
    def _async_update_devices() -> None:
        # Disabled trackers get no coordinator updates, so rename devices here
        for client in coordinator.data.values():
            if (
                client.name
                and (
                    device_entry := device_registry.async_get_device_by_connection(
                        (dr.CONNECTION_NETWORK_MAC, client.phys_address),
                        entry.entry_id,
                    )
                )
                and device_entry.name != client.name
            ):
                device_registry.async_update_device(device_entry.id, name=client.name)
        # An inactive client is only set up if its tracker already exists, so a
        # removed client stays removed until it is active again
        new_keys = [
            key
            for key, client in coordinator.data.items()
            if key not in tracked
            and (
                client.active
                or entity_registry.async_get_entity_id(
                    DEVICE_TRACKER_DOMAIN, DOMAIN, key
                )
            )
        ]
        if new_keys:
            tracked.update(
                (key, dr.format_mac(coordinator.data[key].phys_address))
                for key in new_keys
            )
            async_add_entities(
                SwisscomScannerEntity(coordinator, key) for key in new_keys
            )

    @callback
    def _async_device_removed(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Track a client again if it returns after its device was removed."""
        if TYPE_CHECKING:
            assert event.data["action"] == "remove"
        connections = {tuple(conn) for conn in event.data["device"]["connections"]}
        for key, mac in list(tracked.items()):
            if (dr.CONNECTION_NETWORK_MAC, mac) in connections:
                del tracked[key]

    @callback
    def _is_own_device_removed(event_data: dr.EventDeviceRegistryUpdatedData) -> bool:
        return (
            event_data["action"] == "remove"
            and event_data["device"]["config_entry_id"] == entry.entry_id
        )

    _async_update_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    entry.async_on_unload(
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            _async_device_removed,
            event_filter=_is_own_device_removed,
        )
    )


class SwisscomScannerEntity(
    CoordinatorEntity[SwisscomDataUpdateCoordinator], ScannerEntity
):
    """A device tracked by the Swisscom Internet-Box."""

    def __init__(self, coordinator: SwisscomDataUpdateCoordinator, key: str) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = key
        connection = (dr.CONNECTION_NETWORK_MAC, self.mac_address)
        if self.hostname:
            self._attr_device_info = DeviceInfo(
                connections={connection}, name=self.hostname
            )
        elif dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
        ):
            # Don't overwrite the name of an existing device with the MAC address
            self._attr_device_info = DeviceInfo(connections={connection})
        else:
            self._attr_device_info = DeviceInfo(
                connections={connection}, name=self.mac_address
            )

    @property
    def _device(self):
        return self.coordinator.data.get(self._key)

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether the device is currently connected to the LAN."""
        device = self._device
        return bool(device and device.active)

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        device = self._device
        return device.phys_address if device else self._key

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        device = self._device
        return device.name if device else None

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        device = self._device
        return device.ip_address if device else None
