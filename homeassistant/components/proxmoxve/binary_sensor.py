"""Binary sensor to read Proxmox VE data."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, ProxmoxEntity
from .const import CONF_LXC, CONF_NODE, CONF_QEMU, ProxmoxType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""

    sensors = []
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]

    node = config_entry.data[CONF_NODE]

    proxmox_version = None
    coordinator = coordinators[node][ProxmoxType.Proxmox]
    if not (coordinator_data := coordinator.data) is None:
        proxmox_version = coordinator_data["version"]

    for vm_id in config_entry.data[CONF_QEMU]:
        coordinator = coordinators[node][vm_id]
        coordinator_data = coordinator.data

        # unfound vm case
        if (coordinator_data := coordinator.data) is None:
            continue

        vm_name = coordinator_data["name"]
        vm_sensor = create_binary_sensor(
            coordinator,
            node,
            ProxmoxType.QEMU.upper(),
            vm_id,
            vm_name,
            proxmox_version,
            config_entry,
        )
        sensors.append(vm_sensor)

    for container_id in config_entry.data[CONF_LXC]:
        coordinator = coordinators[node][container_id]
        coordinator_data = coordinator.data

        # unfound container case
        if (coordinator_data := coordinator.data) is None:
            continue

        container_name = coordinator_data["name"]
        container_sensor = create_binary_sensor(
            coordinator,
            node,
            ProxmoxType.LXC.upper(),
            container_id,
            container_name,
            proxmox_version,
            config_entry,
        )
        sensors.append(container_sensor)

    async_add_entities(sensors)


def create_binary_sensor(
    coordinator, node_name, proxmox_type, vm_id, name, proxmox_version, config_entry
):
    """Create a binary sensor based on the given data."""
    return ProxmoxBinarySensor(
        coordinator=coordinator,
        unique_id=f"proxmox_{config_entry.data[CONF_HOST]}{config_entry.data[CONF_PORT]}{node_name}{vm_id}_running",
        name=f"{node_name} {name} running",
        icon="",
        node_name=node_name,
        vm_id=vm_id,
        vm_name=name,
        proxmox_type=proxmox_type,
        proxmox_version=proxmox_version,
        config_entry=config_entry,
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
        vm_name,
        proxmox_type,
        proxmox_version,
        config_entry,
    ):
        """Create the binary sensor for vms or containers."""
        super().__init__(coordinator, unique_id, name, icon, node_name, vm_id)

        host = config_entry.data["host"]
        port = config_entry.data["port"]
        host_port_node_vm = f"{host}_{port}_{node_name}_{vm_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=device_registry.DeviceEntryType.SERVICE,
            configuration_url=f"https://{host}:{port}",
            identifiers={(DOMAIN, host_port_node_vm)},
            default_manufacturer="Proxmox VE",
            name=f"{node_name} {vm_name} ({vm_id})",
            default_model=proxmox_type,
            sw_version=proxmox_version,
            hw_version=None,
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
