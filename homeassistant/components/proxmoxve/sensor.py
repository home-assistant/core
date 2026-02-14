"""Sensor to read Proxmox VE storage disk space."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import CONF_HOST, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import ProxmoxConfigEntry
from .const import CONF_NODE, CONF_NODES, NODE_STORAGE_KEY

BYTES_TO_GIB = 1 / (1024**3)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up storage sensors."""
    sensors: list[ProxmoxStorageSensor] = []
    host_name = entry.data[CONF_HOST]
    coordinators = entry.runtime_data[host_name]

    for node_config in entry.data[CONF_NODES]:
        node_name = node_config[CONF_NODE]
        coord = coordinators[node_name].get(NODE_STORAGE_KEY)
        if coord is None or coord.data is None:
            continue
        storage_coordinator = cast(
            DataUpdateCoordinator[list[dict[str, Any]] | None], coord
        )
        storage_data = storage_coordinator.data
        assert storage_data is not None
        sensors.extend(
            ProxmoxStorageSensor(
                coordinator=storage_coordinator,
                host_name=host_name,
                node_name=node_name,
                storage_id=storage_info["storage"],
                storage_type=storage_info.get("type", ""),
            )
            for storage_info in storage_data
        )

    async_add_entities(sensors)


class ProxmoxStorageSensor(
    CoordinatorEntity[DataUpdateCoordinator[list[dict[str, Any]] | None]],
    SensorEntity,
):
    """Sensor for one Proxmox node storage (state = % free, attributes = sizes)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[dict[str, Any]] | None],
        host_name: str,
        node_name: str,
        storage_id: str,
        storage_type: str,
    ) -> None:
        """Create the storage sensor."""
        super().__init__(coordinator)
        self._host_name = host_name
        self._node_name = node_name
        self._storage_id = storage_id
        self._storage_type = storage_type
        self._attr_name = f"{node_name}_{storage_id} Disk Free"
        self._attr_unique_id = f"proxmox_{host_name}_{node_name}_{storage_id}_disk_used"

    @property
    def native_value(self) -> float | None:
        """Return free space as percentage."""
        if self.coordinator.data is None:
            return None
        for item in self.coordinator.data:
            if item.get("storage") == self._storage_id:
                total = item.get("total") or 0
                avail = item.get("avail")
                if total and total > 0 and avail is not None:
                    return round(100.0 * avail / total, 1)
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        """Return total_gib, free_gib, percent_used and used_gib."""
        if self.coordinator.data is None:
            return {
                "total_gib": None,
                "free_gib": None,
                "percent_used": None,
                "used_gib": None,
            }
        for item in self.coordinator.data:
            if item.get("storage") == self._storage_id:
                total = item.get("total") or 0
                used = item.get("used") or 0
                avail = item.get("avail") or 0
                total_gib = round(total * BYTES_TO_GIB, 2) if total else None
                free_gib = round(avail * BYTES_TO_GIB, 2) if avail is not None else None
                used_gib = round(used * BYTES_TO_GIB, 2) if used is not None else None
                percent_used = (
                    round(100.0 * used / total, 1) if total and total > 0 else None
                )
                return {
                    "total_gib": total_gib,
                    "free_gib": free_gib,
                    "percent_used": percent_used,
                    "used_gib": used_gib,
                }
        return {
            "total_gib": None,
            "free_gib": None,
            "percent_used": None,
            "used_gib": None,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.native_value is not None
        )
