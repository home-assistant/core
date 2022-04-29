"""Support for System Bridge sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
    DATA_GIGABYTES,
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_GIGAHERTZ,
    FREQUENCY_MEGAHERTZ,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from . import SystemBridgeDeviceEntity
from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

ATTR_AVAILABLE: Final = "available"
ATTR_FILESYSTEM: Final = "filesystem"
ATTR_MOUNT: Final = "mount"
ATTR_SIZE: Final = "size"
ATTR_TYPE: Final = "type"
ATTR_USED: Final = "used"

PIXELS: Final = "px"


@dataclass
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


BASE_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="cpu_speed",
        name="CPU Speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=FREQUENCY_GIGAHERTZ,
        icon="mdi:speedometer",
        value=lambda data: round(data["cpu"]["frequency_current"] / 1000, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_temperature",
        name="CPU Temperature",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        value=lambda data: data["cpu"]["temperature"],
    ),
    SystemBridgeSensorEntityDescription(
        key="cpu_voltage",
        name="CPU Voltage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value=lambda data: data["cpu"]["voltage"],
    ),
    # SystemBridgeSensorEntityDescription(
    #     key="displays_connected",
    #     name="Displays Connected",
    #     state_class=SensorStateClass.MEASUREMENT,
    #     icon="mdi:monitor",
    #     value=lambda data: len(data["display"]["connected"]),
    # ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        name="Kernel",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value=lambda data: data["system"]["platform"],
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        name="Memory Free",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda data: round(data["memory"]["virtual_free"] / 1000**3, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        name="Memory Used %",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        value=lambda data: data["memory"]["virtual_percent"],
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        name="Memory Used",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda data: round(data["memory"]["virtual_used"] / 1000**3, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        name="Operating System",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value=lambda data: f"{data['system']['platform']} {data['system']['platform_version']}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        name="Load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda data: data["cpu"]["usage"],
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        name="Version",
        icon="mdi:counter",
        value=lambda data: data["system"]["version"],
    ),
    SystemBridgeSensorEntityDescription(
        key="version_latest",
        name="Latest Version",
        icon="mdi:counter",
        value=lambda data: data["system"]["version_latest"],
    ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: data["battery"]["percentage"],
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        name="Battery Time Remaining",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: utcnow()
        + timedelta(seconds=data["battery"]["sensors_secsleft"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up System Bridge sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for description in BASE_SENSOR_TYPES:
        entities.append(
            SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
        )

    for key, _ in coordinator.data["disk"].items():
        if "_percent" in key.lower():
            partition = key.replace("usage_", "").replace("_percent", "")
            entities.append(
                SystemBridgeSensor(
                    coordinator,
                    SystemBridgeSensorEntityDescription(
                        key=f"filesystem_{partition.replace(':', '')}",
                        name=f"{partition} Space Used",
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        icon="mdi:harddisk",
                        value=lambda data, i=key: data["disk"][i],
                    ),
                    entry.data[CONF_PORT],
                )
            )

    if (
        coordinator.data["battery"]
        and coordinator.data["battery"]["percentage"]
        and coordinator.data["battery"]["percentage"] > -1
    ):
        for description in BATTERY_SENSOR_TYPES:
            entities.append(
                SystemBridgeSensor(coordinator, description, entry.data[CONF_PORT])
            )

    # for index, _ in enumerate(coordinator.data.display.displays):
    #     name = index + 1
    #     entities = [
    #         *entities,
    #         SystemBridgeSensor(
    #             coordinator,
    #             SystemBridgeSensorEntityDescription(
    #                 key=f"display_{name}_resolution_x",
    #                 name=f"Display {name} Resolution X",
    #                 state_class=SensorStateClass.MEASUREMENT,
    #                 native_unit_of_measurement=PIXELS,
    #                 icon="mdi:monitor",
    #                 value=lambda data, i=index: bridge.display.displays[
    #                     i
    #                 ].resolutionX,
    #             ),
    #             entry.data[CONF_PORT],
    #         ),
    #         SystemBridgeSensor(
    #             coordinator,
    #             SystemBridgeSensorEntityDescription(
    #                 key=f"display_{name}_resolution_y",
    #                 name=f"Display {name} Resolution Y",
    #                 state_class=SensorStateClass.MEASUREMENT,
    #                 native_unit_of_measurement=PIXELS,
    #                 icon="mdi:monitor",
    #                 value=lambda data, i=index: bridge.display.displays[
    #                     i
    #                 ].resolutionY,
    #             ),
    #             entry.data[CONF_PORT],
    #         ),
    #         SystemBridgeSensor(
    #             coordinator,
    #             SystemBridgeSensorEntityDescription(
    #                 key=f"display_{name}_refresh_rate",
    #                 name=f"Display {name} Refresh Rate",
    #                 state_class=SensorStateClass.MEASUREMENT,
    #                 native_unit_of_measurement=FREQUENCY_HERTZ,
    #                 icon="mdi:monitor",
    #                 value=lambda data, i=index: bridge.display.displays[
    #                     i
    #                 ].currentRefreshRate,
    #             ),
    #             entry.data[CONF_PORT],
    #         ),
    #     ]

    gpus = []
    for key, value in coordinator.data["gpu"].items():
        if "_name" in key:
            gpus.append({"key": key.replace("_name", ""), "name": value})

    for index, gpu in enumerate(gpus):
        gpu_key = gpu["key"]
        gpu_name = gpu["name"]

        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_core_clock_speed",
                    name=f"{gpu_name} Clock Speed",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
                    icon="mdi:speedometer",
                    value=lambda data, k=gpu_key: round(
                        data["gpu"][f"{k}_core_clock"], 2
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_clock_speed",
                    name=f"{gpu_name} Memory Clock Speed",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
                    icon="mdi:speedometer",
                    value=lambda data, k=gpu_key: round(
                        data["gpu"][f"{k}_memory_clock"], 2
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_free",
                    name=f"{gpu_name} Memory Free",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=DATA_GIGABYTES,
                    icon="mdi:memory",
                    value=lambda data, k=gpu_key: round(
                        data["gpu"][f"{k}_memory_free"] / 10**3, 2
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_used_percentage",
                    name=f"{gpu_name} Memory Used %",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:memory",
                    value=lambda data, k=gpu_key: round(
                        (
                            data["gpu"][f"{k}_memory_used"]
                            / data["gpu"][f"{k}_memory_total"]
                        )
                        * 100,
                        2,
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_memory_used",
                    name=f"{gpu_name} Memory Used",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=DATA_GIGABYTES,
                    icon="mdi:memory",
                    value=lambda data, k=gpu_key: round(
                        data["gpu"][f"{k}_memory_used"] / 10**3, 2
                    ),
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_fan_speed",
                    name=f"{gpu_name} Fan Speed",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:fan",
                    value=lambda data, k=gpu_key: data["gpu"][f"{k}_fan_speed"],
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_power_usage",
                    name=f"{gpu_name} Power Usage",
                    entity_registry_enabled_default=False,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=POWER_WATT,
                    value=lambda data, k=gpu_key: data["gpu"][f"{k}_power"],
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_temperature",
                    name=f"{gpu_name} Temperature",
                    entity_registry_enabled_default=False,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=TEMP_CELSIUS,
                    value=lambda data, k=gpu_key: data["gpu"][f"{k}_temperature"],
                ),
                entry.data[CONF_PORT],
            ),
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"gpu_{index}_usage_percentage",
                    name=f"{gpu_name} Usage %",
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda data, k=gpu_key: data["gpu"][f"{k}_core_load"],
                ),
                entry.data[CONF_PORT],
            ),
        ]

    for index in range(coordinator.data["cpu"]["count"]):
        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}",
                    name=f"Load CPU {index}",
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:percent",
                    value=lambda data, index=index: data["cpu"][f"usage_{index}"],
                ),
                entry.data[CONF_PORT],
            ),
        ]

    async_add_entities(entities)


class SystemBridgeSensor(SystemBridgeDeviceEntity, SensorEntity):
    """Define a System Bridge sensor."""

    entity_description: SystemBridgeSensorEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeSensorEntityDescription,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api_port,
            description.key,
            description.name,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        try:
            return cast(StateType, self.entity_description.value(self.coordinator.data))
        except TypeError:
            return None
