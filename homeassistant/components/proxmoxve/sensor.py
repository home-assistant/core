"""Sensor to read Proxmox VE data."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DATA_GIBIBYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, PROXMOX_CLIENTS, ProxmoxEntity

BYTE_TO_GIBIBYTE = 1.074e9


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up sensors."""

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

                name = coordinator_data.name

                sensors += [
                    ProxmoxSensor(
                        coordinator=coordinator,
                        unique_id=f"proxmox_{node_name}_{dev_id}_mem_gib",
                        name=f"{node_name}_{name}_memory",
                        icon="",
                        host_name=host_name,
                        node_name=node_name,
                        vm_id=dev_id,
                        native_lambda=lambda data: round(
                            int(data.mem) / BYTE_TO_GIBIBYTE, 2
                        ),
                        unit_of_measurement=DATA_GIBIBYTES,
                    )
                ]

    add_entities(sensors)


class ProxmoxSensor(ProxmoxEntity, SensorEntity):
    """A sensor for reading Proxmox VE data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id,
        name,
        icon,
        host_name,
        node_name,
        vm_id,
        native_lambda,
        unit_of_measurement,
    ):
        """Create the sensor for vms or containers."""

        self.native_lambda = native_lambda
        self._attr_native_unit_of_measurement = unit_of_measurement
        super().__init__(
            coordinator, unique_id, name, icon, host_name, node_name, vm_id
        )

    @property
    def native_value(self):
        """Get the native value."""

        if (data := self.coordinator.data) is None:
            return None

        return self.native_lambda(data)
