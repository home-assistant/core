"""Platform for device tracker integration."""
from __future__ import annotations

from devolo_plc_api.device import Device

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONNECTED_STATIONS, CONNECTED_WIFI_CLIENTS, DOMAIN, MAC_ADDRESS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "coordinators"
    ]
    registry = await entity_registry.async_get_registry(hass)
    tracked = set()

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        new_entities = []
        for station in coordinators[CONNECTED_WIFI_CLIENTS].data[CONNECTED_STATIONS]:
            if station[MAC_ADDRESS] in tracked:
                continue

            new_entities.append(
                DevoloScannerEntity(
                    coordinators[CONNECTED_WIFI_CLIENTS], station[MAC_ADDRESS]
                )
            )
            tracked.add(station[MAC_ADDRESS])
            if new_entities:
                async_add_entities(new_entities)

    @callback
    def restore_entities() -> None:
        """Restore clients that are not a part of active clients list."""
        missing = []
        for entity in registry.entities.values():
            if (
                entity.config_entry_id == entry.entry_id
                and entity.platform == DOMAIN
                and entity.domain == DEVICE_TRACKER_DOMAIN
                and entity.unique_id not in tracked
            ):
                missing.append(
                    DevoloScannerEntity(
                        coordinators[CONNECTED_WIFI_CLIENTS], entity.unique_id
                    )
                )
                tracked.add(entity.unique_id)

        if missing:
            async_add_entities(missing)

    if device.device and "wifi1" in device.device.features:
        entry.async_on_unload(
            coordinators[CONNECTED_WIFI_CLIENTS].async_add_listener(new_device_callback)
        )
        new_device_callback()
        restore_entities()


class DevoloScannerEntity(CoordinatorEntity, ScannerEntity):
    """Representation of a devolo device tracker."""

    def __init__(self, coordinator: DataUpdateCoordinator, mac: str) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._mac = mac

    @property
    def icon(self) -> str:
        """Return device icon."""
        if self.is_connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return bool(
            [
                station
                for station in self.coordinator.data[CONNECTED_STATIONS]
                if station[MAC_ADDRESS] == self.mac_address
            ]
        )

    @property
    def mac_address(self) -> str:
        """Return mac_address."""
        return self._mac

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER
