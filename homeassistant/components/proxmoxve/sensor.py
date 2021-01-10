"""Sensors to read Proxmox VE data."""
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATOR, DOMAIN, IGNORED, ProxmoxEntity

DIVISOR_GIB = 1.074e9
DIVISOR_HOUR = 60 * 60

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform."""
    if discovery_info is None:
        return

    coordinator = hass.data[DOMAIN][COORDINATOR]
    sensors = []

    for host_config in discovery_info["config"][DOMAIN]:
        host_name = host_config["host"]

        for node_config in host_config["nodes"]:
            node_name = node_config["node"]

            if node_name in hass.data[DOMAIN][IGNORED]:
                continue

            node_memory = ProxmoxNodeMemorySensor(
                coordinator=coordinator,
                unique_id=f"proxmox_{node_name}_memory_used",
                name=f"{node_name}_memory_used",
                icon="mdi:memory",
                unit_of_measurement="%",
                host_name=host_name,
                node_name=node_name,
                vm_id=None,
            )

            node_rootfs = ProxmoxNodeRootfsSensor(
                coordinator=coordinator,
                unique_id=f"proxmox_{node_name}_rootfs_used",
                name=f"{node_name}_rootfs_used",
                icon="mdi:memory",
                unit_of_measurement="%",
                host_name=host_name,
                node_name=node_name,
                vm_id=None,
            )

            sensors.append(node_memory)
            sensors.append(node_rootfs)

            for vm_id in node_config["vms"]:
                if vm_id in hass.data[DOMAIN][IGNORED]:
                    continue

                vm_name = coordinator.data[host_name][node_name][vm_id]["name"]

                add_entities(
                    create_sensors_container_vm(
                        coordinator, host_name, node_name, vm_name, vm_id
                    )
                )

            for container_id in node_config["containers"]:
                if container_id in hass.data[DOMAIN][IGNORED]:
                    continue

                container_name = coordinator.data[host_name][node_name][container_id][
                    "name"
                ]

                add_entities(
                    create_sensors_container_vm(
                        coordinator, host_name, node_name, container_name, container_id
                    )
                )

    add_entities(sensors)


def create_sensors_container_vm(
    coordinator,
    host_name,
    node_name,
    vm_name,
    vm_id,
):
    """Create and return a list of created sensor objects for containers or vms."""

    sensors = []

    memory = ProxmoxVmMemorySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_memory_used",
        name=f"{node_name}_{vm_name}_memory_used",
        icon="mdi:memory",
        unit_of_measurement="%",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )
    sensors.append(memory)

    net_in = ProxmoxVmNetworkInSensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_network_in",
        name=f"{node_name}_{vm_name}_network_in",
        icon="mdi:download-network",
        unit_of_measurement="k",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )
    sensors.append(net_in)

    net_out = ProxmoxVmNetworkOutSensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_network_out",  # TODO
        name=f"{node_name}_{vm_name}_network_out",
        icon="mdi:upload-network",
        unit_of_measurement="k",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )
    sensors.append(net_out)

    cpu_use = ProxmoxVmCpuSensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_cpu_use",  # TODO
        name=f"{node_name}_{vm_name}_cpu_use",
        icon="mdi:cpu-64-bit",
        unit_of_measurement="%",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )
    sensors.append(cpu_use)

    uptime = ProxmoxVmUptimeSensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{node_name}_{vm_id}_uptime",  # TODO
        name=f"{node_name}_{vm_name}_uptime",
        icon="mdi:timer-outline",
        unit_of_measurement="Hours",
        host_name=host_name,
        node_name=node_name,
        vm_id=vm_id,
    )
    sensors.append(uptime)

    return sensors


class ProxmoxSensor(ProxmoxEntity):
    """Represents a sensor created for the Proxmox VE platform."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id=None,
    ):
        """Create a Proxmox Sensor Entity."""
        super().__init__(
            coordinator, unique_id, name, icon, host_name, node_name, vm_id
        )

        self._unit_of_measurement = unit_of_measurement

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement


class ProxmoxNodeMemorySensor(ProxmoxSensor):
    """Represents the memory used of a proxmox node."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id=None,
    ):
        """Create a node memory sensor."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        used = self.coordinator.data[self._host_name][self._node_name]["memory_used"]
        total = self.coordinator.data[self._host_name][self._node_name]["memory_total"]
        return "%.2f" % (100 * (used / total))

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""

        node = self.coordinator.data[self._host_name][self._node_name]
        data = {
            "memory_used": "%.2f" % (node["memory_used"] / DIVISOR_GIB),
            "memory_total": "%.2f" % (node["memory_total"] / DIVISOR_GIB),
        }

        return data


class ProxmoxNodeRootfsSensor(ProxmoxSensor):
    """Represents the root filesystem of a proxmox node."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id=None,
    ):
        """Create a root filesystem sensor for a node."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name]
        return "%.2f" % (100 * (data["rootfs_used"] / data["rootfs_total"]))

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""

        data = self.coordinator.data[self._host_name][self._node_name]
        data = {
            "rootfs_used": "%.2f" % (data["rootfs_used"] / DIVISOR_GIB),
            "rootfs_total": "%.2f" % (data["rootfs_total"] / DIVISOR_GIB),
        }

        return data


class ProxmoxVmMemorySensor(ProxmoxSensor):
    """Represents the memory used of a proxmox virtual machine."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id=None,
    ):
        """Create a vm memory sensor."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        return "%.2f" % (100 * (data["memory_used"] / data["memory_total"]))

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""

        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]

        return {
            "memory_used": "%.2f" % (data["memory_used"] / DIVISOR_GIB),
            "memory_total": "%.2f" % (data["memory_total"] / DIVISOR_GIB),
        }


class ProxmoxVmNetworkInSensor(ProxmoxSensor):
    """Represents the network in of a proxmox virtual machine."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id,
    ):
        """Create a vm network input sensor."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        return "%.2f" % (data["net_in"] / 1000)


class ProxmoxVmNetworkOutSensor(ProxmoxSensor):
    """Represents the network out of a proxmox virtual machine."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id,
    ):
        """Create a vm network output sensor."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        return "%.2f" % (data["net_out"] / 1000)


class ProxmoxVmCpuSensor(ProxmoxSensor):
    """Represents the cpu of a proxmox virtual machine."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id,
    ):
        """Create a vm cpu usage sensor."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        return "%.2f" % (data["cpu_use"] * 100)

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]

        return {"num_cpu": data["num_cpu"]}


class ProxmoxVmUptimeSensor(ProxmoxSensor):
    """Represents the uptime of a proxmox virtual machine."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        unit_of_measurement,
        host_name,
        node_name,
        vm_id,
    ):
        """Create a vm uptime sensor."""
        super().__init__(
            coordinator,
            unique_id,
            name,
            icon,
            unit_of_measurement,
            host_name,
            node_name,
            vm_id,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        return "%.2f" % (data["uptime"] / DIVISOR_HOUR)

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""

        data = self.coordinator.data[self._host_name][self._node_name][self._vm_id]
        hours = data["uptime"] / DIVISOR_HOUR
        return {"days": "%.2f" % (hours / 24.0), "months": "%.2f" % (hours / 24.0 / 30)}
