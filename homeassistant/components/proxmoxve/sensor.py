"""Sensor to read Proxmox VE data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import DATA_GIBIBYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import COORDINATORS, DOMAIN, PROXMOX_CLIENTS, ProxmoxEntity

BYTE_TO_GIBIBYTE = 1.074e9


@dataclass
class ProxmoxVERequiredKeyMixin:
    """Mixin for required lambda functions."""

    native_lambda: Callable


@dataclass
class ProxmoxVESensorEntityDescription(
    SensorEntityDescription, ProxmoxVERequiredKeyMixin
):
    """Class to describe a proxmoxve sensor."""


SENSOR_DESCRIPTIONS = [
    (
        ProxmoxVESensorEntityDescription(
            key="mem_gib",
            name="mem_gib",
            native_unit_of_measurement=DATA_GIBIBYTES,
            native_lambda=lambda data: round(int(data.mem) / BYTE_TO_GIBIBYTE, 2),
        )
    ),
]


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

                for description in SENSOR_DESCRIPTIONS:
                    sensors.append(
                        ProxmoxSensor(
                            coordinator=coordinator,
                            vm_name=name,
                            host_name=host_name,
                            node_name=node_name,
                            vm_id=dev_id,
                            description=description,
                        )
                    )

    add_entities(sensors)


class ProxmoxSensor(ProxmoxEntity, SensorEntity):
    """A sensor for reading Proxmox VE data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        vm_name: str,
        host_name: str,
        node_name: str,
        vm_id: int,
        description: ProxmoxVESensorEntityDescription,
    ) -> None:
        """Create the sensor for vms or containers."""

        self.native_lambda = description.native_lambda
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        super().__init__(
            coordinator,
            unique_id=f"proxmox_{node_name}_{vm_id}_{description.name}",
            name=f"{node_name}_{vm_name}_{description.name}",
            icon=description.icon,
            host_name=host_name,
            node_name=node_name,
            vm_id=vm_id,
        )

    @property
    def native_value(self) -> float | None:
        """Get the native value."""

        if (data := self.coordinator.data) is None:
            return None

        return self.native_lambda(data)
