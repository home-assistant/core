"""Binary sensor to read Proxmox VE data."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, PROXMOX_CLIENTS, ProxmoxEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up binary sensors."""
    if discovery_info is None:
        return

    sensors = []

    for host_config in discovery_info["config"][DOMAIN]:
        host_name = host_config["host"]
        host_name_coordinators = hass.data[DOMAIN][COORDINATORS][host_name]

        if hass.data[PROXMOX_CLIENTS][host_name] is None:
            continue

        for node_config in host_config["nodes"]:
            node_name = node_config["node"]

            for dev_id in node_config["vms"] + node_config["containers"]:
                coordinator = host_name_coordinators[node_name][dev_id]

                # unfound case
                if (coordinator_data := coordinator.data) is None:
                    continue

                name = coordinator_data["name"]
                sensor = create_binary_sensor(
                    coordinator, host_name, node_name, dev_id, name
                )
                sensors.append(sensor)

    add_entities(sensors)


def create_binary_sensor(coordinator, host_name, node_name, vm_id, name):
    """Create a binary sensor based on the given data."""
    return ProxmoxBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_running",
        name=f"{node_name}_{name}",
        icon="",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )


class ProxmoxBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE data."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        host_name,
        node_name,
        vm_id,
    ):
        """Create the binary sensor for vms or containers."""
        super().__init__(
            coordinator, unique_id, name, icon, host_name, node_name, vm_id
        )

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        if (data := self.coordinator.data) is None:
            return None

        return data["status"] == "running"

    @property
    def available(self):
        """Return sensor availability."""

        return super().available and self.coordinator.data is not None
