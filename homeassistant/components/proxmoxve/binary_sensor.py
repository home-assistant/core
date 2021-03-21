"""Binary sensor to read Proxmox VE data."""
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATOR, DOMAIN, ProxmoxEntity


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up binary sensors."""
    if discovery_info is None:
        return

    coordinator = hass.data[DOMAIN][COORDINATOR]

    sensors = []

    for host_config in discovery_info["config"][DOMAIN]:
        host_name = host_config["host"]

        for node_config in host_config["nodes"]:
            node_name = node_config["node"]

            for vm_id in node_config["vms"]:
                coordinator_data = coordinator.data[host_name][node_name][vm_id]

                # unfound vm case
                if coordinator_data is None:
                    continue

                vm_name = coordinator_data["name"]
                vm_status = create_binary_sensor(
                    coordinator, host_name, node_name, vm_id, vm_name
                )
                sensors.append(vm_status)

            for container_id in node_config["containers"]:
                coordinator_data = coordinator.data[host_name][node_name][container_id]

                # unfound container case
                if coordinator_data is None:
                    continue

                container_name = coordinator_data["name"]
                container_status = create_binary_sensor(
                    coordinator, host_name, node_name, container_id, container_name
                )
                sensors.append(container_status)

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


class ProxmoxBinarySensor(ProxmoxEntity):
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

        self._state = None

    @property
    def state(self):
        """Return the state of the binary sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        if data["status"] == "running":
            return STATE_ON
        return STATE_OFF
