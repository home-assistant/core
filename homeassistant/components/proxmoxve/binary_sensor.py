"""Binary sensor to read Proxmox VE data."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, PROXMOX_CLIENTS, ProxmoxEntity


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
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

            for vm_id in node_config["vms"]:
                coordinator = host_name_coordinators[node_name][vm_id]
                coordinator_data = coordinator.data

                # unfound vm case
                if coordinator_data is None:
                    continue

                vm_name = coordinator_data["name"]
                vm_sensor = create_binary_sensor(
                    coordinator, host_name, node_name, vm_id, vm_name
                )
                sensors.append(vm_sensor)

            for container_id in node_config["containers"]:
                coordinator = host_name_coordinators[node_name][container_id]
                coordinator_data = coordinator.data

                # unfound container case
                if coordinator_data is None:
                    continue

                container_name = coordinator_data["name"]
                container_sensor = create_binary_sensor(
                    coordinator, host_name, node_name, container_id, container_name
                )
                sensors.append(container_sensor)

    add_entities(sensors)


def create_binary_sensor(coordinator, host_name, node_name, vm_id, name):
    """Create a binary sensor based on the given data."""
    return ProxmoxBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_running",
        name=f"{node_name}_{name}_running",
        icon="",
        host_name=host_name,
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
        data = self.coordinator.data

        if data is None:
            return None

        return data["status"] == "running"

    @property
    def available(self):
        """Return sensor availability."""

        return super().available and self.coordinator.data is not None
