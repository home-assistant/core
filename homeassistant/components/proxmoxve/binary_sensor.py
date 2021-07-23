"""Binary sensor to read Proxmox VE data."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, ProxmoxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up binary sensors."""

    sensors = []
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]

    for node_config in config_entry.data["nodes"]:
        node_name = node_config["name"]

        for vm_id in node_config["vms"]:
            coordinator = coordinators[node_name][vm_id]
            coordinator_data = coordinator.data

            # unfound vm case
            if (coordinator_data := coordinator.data) is None:
                continue

            vm_name = coordinator_data["name"]
            vm_sensor = create_binary_sensor(coordinator, node_name, vm_id, vm_name)
            sensors.append(vm_sensor)

        for container_id in node_config["containers"]:
            coordinator = coordinators[node_name][container_id]
            coordinator_data = coordinator.data

            # unfound container case
            if (coordinator_data := coordinator.data) is None:
                continue

            container_name = coordinator_data["name"]
            container_sensor = create_binary_sensor(
                coordinator, node_name, container_id, container_name
            )
            sensors.append(container_sensor)

    async_add_entities(sensors)


def create_binary_sensor(coordinator, node_name, vm_id, name):
    """Create a binary sensor based on the given data."""
    return ProxmoxBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_running",
        name=f"{node_name}_{name}_running",
        icon="",
        node_name=node_name,
        vm_id=vm_id,
    )


class ProxmoxBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        node_name,
        vm_id,
    ):
        """Create the binary sensor for vms or containers."""
        super().__init__(coordinator, unique_id, name, icon, node_name, vm_id)

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
