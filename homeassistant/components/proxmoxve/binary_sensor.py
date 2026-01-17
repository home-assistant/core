"""Binary sensor to read Proxmox VE data."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CONTAINERS, CONF_NODE, CONF_NODES, CONF_VMS
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator
from .entity import ProxmoxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data

    sensors: list[ProxmoxBinarySensor] = []
    for node_config in entry.data[CONF_NODES]:
        node_name = node_config[CONF_NODE]
        node_data = coordinator.data.nodes.get(node_name)
        if node_data is None:
            continue

        sensors.extend(
            ProxmoxBinarySensor(
                coordinator=coordinator,
                host_name=entry.data[CONF_HOST],
                node_name=node_name,
                vm_id=vm_id,
                name=vm_data.get("name", str(vm_id)),
            )
            for vm_id in node_config[CONF_VMS]
            if (vm_data := node_data.vms.get(vm_id))
        )

        sensors.extend(
            ProxmoxBinarySensor(
                coordinator=coordinator,
                host_name=entry.data[CONF_HOST],
                node_name=node_name,
                vm_id=container_id,
                name=container_data.get("name", str(container_id)),
            )
            for container_id in node_config[CONF_CONTAINERS]
            if (container_data := node_data.containers.get(container_id))
        )

    async_add_entities(sensors)


class ProxmoxBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE data."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: ProxmoxCoordinator,
        host_name: str,
        node_name: str,
        vm_id: int,
        name: str,
    ) -> None:
        """Create the binary sensor for vms or containers."""
        super().__init__(
            coordinator,
            unique_id=f"proxmox_{node_name}_{vm_id}_running",
            name=f"{node_name}_{name}",
            icon="",
            host_name=host_name,
            node_name=node_name,
            vm_id=vm_id,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if (data := self.coordinator.data) is None:
            return None

        if (vm_id := self._vm_id) is None:
            return None

        node_data = data.nodes.get(self._node_name)
        if node_data is None:
            return None

        resource_data = node_data.vms.get(vm_id) or node_data.containers.get(vm_id)
        if resource_data is None:
            return None

        return resource_data.get("status") == "running"

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return super().available and self.coordinator.data is not None
