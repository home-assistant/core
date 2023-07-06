"""Binary sensor to read Proxmox VE data."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.proxmoxve.coordinator import ProxmoxDataUpdateCoordinator
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_STATUS_COMMAND,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_VMS,
    COORDINATORS,
    DOMAIN,
    PROXMOX_CLIENTS,
    SERVICE_SET_VM_STATUS,
    StatusCommand,
)
from .entity import ProxmoxEntity


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
        host_name = host_config[CONF_HOST]
        host_name_coordinators = hass.data[DOMAIN][COORDINATORS][host_name]

        if hass.data[PROXMOX_CLIENTS][host_name] is None:
            continue

        for node_config in host_config[CONF_NODES]:
            node_name = node_config[CONF_NODE]

            for dev_id in node_config[CONF_VMS] + node_config[CONF_CONTAINERS]:
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

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_VM_STATUS,
        cv.make_entity_service_schema(
            {vol.Required(ATTR_STATUS_COMMAND): vol.Coerce(StatusCommand)}
        ),
        "async_set_status",
    )


def create_binary_sensor(
    coordinator: ProxmoxDataUpdateCoordinator,
    host_name: str,
    node_name: str,
    vm_id: int,
    name: str,
) -> ProxmoxBinarySensor:
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
        coordinator: ProxmoxDataUpdateCoordinator,
        unique_id: str,
        name: str,
        icon: str,
        host_name: str,
        node_name: str,
        vm_id: int,
    ) -> None:
        """Create the binary sensor for vms or containers."""
        super().__init__(
            coordinator, unique_id, name, icon, host_name, node_name, vm_id
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if (data := self.coordinator.data) is None:
            return None

        return data["status"] == "running"

    @property
    def available(self) -> bool:
        """Return sensor availability."""

        return super().available and self.coordinator.data is not None

    async def async_set_status(self, status_command: StatusCommand):
        """Service to set vm status."""
        await self.coordinator.set_vm_status(status_command)
