"""Sensor to read Proxmox VE data."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    PROXMOX_CLIENTS,
    PROXMOX_SENSOR_TYPES_ALL,
)
from .model import ProxmoxSensorDescription


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up sensors."""
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

                for description in PROXMOX_SENSOR_TYPES_ALL:
                    sensors.append(
                        create_sensor(
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
                for description in PROXMOX_SENSOR_TYPES_ALL:
                    sensors.append(
                        create_sensor(
                            coordinator=coordinator,
                            device_info=device_info,
                            description=description,
                            node_name=node_name,
                            mid=ct_id,
                            name=ct_name,
                        )
                    )

    add_entities(sensors)


def create_sensor(
    coordinator: DataUpdateCoordinator,
    device_info: DeviceInfo,
    description: ProxmoxSensorDescription,
    node_name: str,
    mid: str,
    name: str,
):
    """Create a sensor based on the given data."""
    return ProxmoxSensor(
        coordinator=coordinator,
        device_info=device_info,
        description=description,
        unique_id=f"proxmox_{node_name}_{mid}_{description.key}",
        name=f"{node_name}_{name}_{description.key}",
    )


class ProxmoxSensor(ProxmoxEntity, SensorEntity):
    """A sensor for reading Proxmox VE data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: DeviceInfo,
        description: ProxmoxSensorDescription,
        name: str,
        unique_id: str,
    ):
        """Create the sensor for vms or containers."""
        super().__init__(
            coordinator=coordinator,
            device_info=device_info,
            name=name,
            unique_id=unique_id,
        )
        self.entity_description = description

    @property
    def native_value(self):
        """Return the units of the sensor."""
        if (data := self.coordinator.data) is None:
            return None

        if self.entity_description.key not in data:
            return None

        native_value = data[self.entity_description.key]

        if self.entity_description.conversion is not None:
            return self.entity_description.conversion(native_value)

        return native_value

    @property
    def available(self):
        """Return sensor availability."""

        return super().available and self.coordinator.data is not None
