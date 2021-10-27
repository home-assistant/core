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
                coordinator = host_name_coordinators[node_name]["machines"][vm_id]

                # unfound vm case
                if (coordinator_data := coordinator.data) is None:
                    continue

                vm_name = coordinator_data["name"]
                vm_sensor = create_machine_binary_sensor(
                    coordinator, host_name, node_name, vm_id, vm_name
                )
                sensors.append(vm_sensor)

            for container_id in node_config["containers"]:
                coordinator = host_name_coordinators[node_name]["machines"][container_id]

                # unfound container case
                if (coordinator_data := coordinator.data) is None:
                    continue

                container_name = coordinator_data["name"]
                container_sensor = create_machine_binary_sensor(
                    coordinator, host_name, node_name, container_id, container_name
                )
                sensors.append(container_sensor)

            coordinator = host_name_coordinators[node_name]["updates"]
            node_updates_sensor = create_node_updates_binary_sensor(
                coordinator, host_name, node_name
            )
            sensors.append(node_updates_sensor)

    add_entities(sensors)


def create_machine_binary_sensor(coordinator, host_name, node_name, vm_id, name):
    """Create a binary sensor for a VM/LXC based on the given data."""
    return ProxmoxMachineBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_running",
        name=f"{node_name}_{name}_running",
        icon="",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )


def create_node_updates_binary_sensor(coordinator, host_name, node_name):
    """Create a binary sensor for node update status based on the given data."""
    return ProxmoxNodeUpdateBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_update_required",
        name=f"{node_name}_update_required",
        icon="",
        host_name=host_name,
        node_name=node_name,
    )


class ProxmoxMachineBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE VM/LXC data."""

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


class ProxmoxNodeUpdateBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE node update data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        host_name,
        node_name
    ):
        """Create the binary sensor for node updates."""
        super().__init__(
            coordinator, unique_id, name, icon, host_name, node_name
        )

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        if (data := self.coordinator.data) is None:
            return None

        return len(data) > 0

    @property
    def available(self):
        """Return sensor availability."""

        return super().available and self.coordinator.data is not None

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""

        if self.coordinator.data is None:
            return None

        data = {}

        for update_item in self.coordinator.data:
            data[update_item["Package"]] = update_item["Version"]

        return data
