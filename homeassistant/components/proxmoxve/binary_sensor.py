"""Binary sensor to read Proxmox VE data."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import ProxmoxEntity, compile_device_info
from .const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_VMS,
    COORDINATORS,
    DOMAIN,
    PROXMOX_BINARYSENSOR_TYPES,
    PROXMOX_CLIENTS,
)
from .model import ProxmoxBinarySensorDescription


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up binary sensors."""
    if discovery_info is None:
        return

    sensors = []

    for host_config in discovery_info["config"][DOMAIN]:
        host_name = host_config[CONF_HOST]
        host_name_coordinators = hass.data[DOMAIN][COORDINATORS][host_name]

        if hass.data[PROXMOX_CLIENTS][host_name] is None:
            continue

        for node_config in host_config[CONF_NODES]:
            node_name = node_config[CONF_NODE]

            for vm_id in node_config[CONF_VMS]:
                coordinator = host_name_coordinators[node_name][vm_id]

                # unfound vm case
                if (coordinator_data := coordinator.data) is None:
                    continue

                vm_name = coordinator_data["name"]
                device_info = compile_device_info(host_name, node_name, vm_id, vm_name)
                for description in PROXMOX_BINARYSENSOR_TYPES:
                    sensors.append(
                        create_binary_sensor(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=vm_id,
                            name=vm_name,
                        )
                    )

            for ct_id in node_config[CONF_CONTAINERS]:
                coordinator = host_name_coordinators[node_name][ct_id]

                # unfound container case
                if (coordinator_data := coordinator.data) is None:
                    continue

                ct_name = coordinator_data["name"]
                device_info = compile_device_info(host_name, node_name, ct_id, ct_name)
                for description in PROXMOX_BINARYSENSOR_TYPES:
                    sensors.append(
                        create_binary_sensor(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=ct_id,
                            name=ct_name,
                        )
                    )

    add_entities(sensors)


def create_binary_sensor(
    coordinator: DataUpdateCoordinator,
    device_info: DeviceInfo,
    description: ProxmoxBinarySensorDescription,
    node_name: str,
    mid: str,
    name: str,
):
    """Create a binary sensor based on the given data."""
    return ProxmoxBinarySensor(
        coordinator=coordinator,
        device_info=device_info,
        description=description,
        unique_id=f"proxmox_{node_name}_{mid}_running",  # Legacy uid kept for non-breaking change
        name=f"{node_name}_{name}_running",
    )


class ProxmoxBinarySensor(ProxmoxEntity, BinarySensorEntity):
    """A binary sensor for reading Proxmox VE data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        description: ProxmoxBinarySensorDescription,
        name: str,
        unique_id: str,
    ):
        """Create the binary sensor for vms or containers."""
        super().__init__(
            coordinator=coordinator,
            device_info=device_info,
            name=name,
            unique_id=unique_id,
        )
        self.entity_description = description

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
