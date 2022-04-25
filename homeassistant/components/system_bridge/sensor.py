"""Support for System Bridge sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    FREQUENCY_GIGAHERTZ,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=FREQUENCY_GIGAHERTZ,
        icon="mdi:speedometer",
        value=lambda data: data["cpu"]["frequency_current"] / 1000,
    ),
    # SystemBridgeSensorEntityDescription(
    #     key="cpu_temperature",
    #     name="CPU Temperature",
    #     entity_registry_enabled_default=False,
    #     device_class=SensorDeviceClass.TEMPERATURE,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     native_unit_of_measurement=TEMP_CELSIUS,
    #     value=lambda data: data["cpu"].temperature.main,
    # ),
    # SystemBridgeSensorEntityDescription(
    #     key="cpu_voltage",
    #     name="CPU Voltage",
    #     entity_registry_enabled_default=False,
    #     device_class=SensorDeviceClass.VOLTAGE,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    #     value=lambda data: data["cpu"].cpu.voltage,
    # ),
    # SystemBridgeSensorEntityDescription(
    #     key="displays_connected",
    #     name="Displays Connected",
    #     state_class=SensorStateClass.MEASUREMENT,
    #     icon="mdi:monitor",
    #     value=lambda data: len(bridge.display.displays),
    # ),
    SystemBridgeSensorEntityDescription(
        key="kernel",
        name="Kernel",
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value=lambda data: data["system"]["platform"],
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_free",
        name="Memory Free",
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda data: round(data["memory"]["virtual_free"] / 1000**3, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used_percentage",
        name="Memory Used %",
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        value=lambda data: data["memory"]["virtual_percent"],
    ),
    SystemBridgeSensorEntityDescription(
        key="memory_used",
        name="Memory Used",
        entity_registry_enabled_default=False,
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:memory",
        value=lambda data: round(data["memory"]["virtual_used"] / 1000**3, 2),
    ),
    SystemBridgeSensorEntityDescription(
        key="os",
        name="Operating System",
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
        value=lambda data: f"{data['system']['platform']} {data['system']['platform_version']}",
    ),
    SystemBridgeSensorEntityDescription(
        key="processes_load",
        name="Load",
        entity_registry_visible_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value=lambda data: data["cpu"]["usage"],
    ),
    SystemBridgeSensorEntityDescription(
        key="version",
        name="Version",
        entity_registry_visible_default=True,
        icon="mdi:counter",
        value=lambda data: data["system"]["version"],
    ),
    # SystemBridgeSensorEntityDescription(
    #     key="version_latest",
    #     name="Latest Version",
    #     icon="mdi:counter",
    #     value=lambda data: data.information.updates.version.new,
    # ),
)

BATTERY_SENSOR_TYPES: tuple[SystemBridgeSensorEntityDescription, ...] = (
    SystemBridgeSensorEntityDescription(
        key="battery",
        name="Battery",
        entity_registry_visible_default=True,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda data: data["battery"]["percentage"],
    ),
    SystemBridgeSensorEntityDescription(
        key="battery_time_remaining",
        name="Battery Time Remaining",
        entity_registry_visible_default=True,
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: str(
            datetime.now()
            + timedelta(minutes=data["battery"]["sensors_time_remaining"])
        ),
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

    # for key, _ in coordinator.data.filesystem.fsSize.items():
    #     uid = key.replace(":", "")
    #     entities.append(
    #         SystemBridgeSensor(
    #             coordinator,
    #             SystemBridgeSensorEntityDescription(
    #                 key=f"filesystem_{uid}",
    #                 name=f"{key} Space Used",
    #                 entity_registry_visible_default=True,
    #                 state_class=SensorStateClass.MEASUREMENT,
    #                 native_unit_of_measurement=PERCENTAGE,
    #                 icon="mdi:harddisk",
    #                 value=lambda data, i=key: round(
    #                     bridge.filesystem.fsSize[i]["use"], 2
    #                 ),
    #             ),
    #             entry.data[CONF_PORT],
    #         )
    #     )

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
    #                 entity_registry_visible_default=True,
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
    #                 entity_registry_visible_default=True,
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
    #                 entity_registry_visible_default=True,
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

    # for index, _ in enumerate(coordinator.data.graphics.controllers):
    #     if coordinator.data.graphics.controllers[index].name is not None:
    #         # Remove vendor from name
    #         name = (
    #             coordinator.data.graphics.controllers[index]
    #             .name.replace(coordinator.data.graphics.controllers[index].vendor, "")
    #             .strip()
    #         )
    #         entities = [
    #             *entities,
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_core_clock_speed",
    #                     name=f"{name} Clock Speed",
    #                     entity_registry_enabled_default=False,
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
    #                     icon="mdi:speedometer",
    #                     value=lambda data, i=index: bridge.graphics.controllers[
    #                         i
    #                     ].clockCore,
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_memory_clock_speed",
    #                     name=f"{name} Memory Clock Speed",
    #                     entity_registry_enabled_default=False,
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=FREQUENCY_MEGAHERTZ,
    #                     icon="mdi:speedometer",
    #                     value=lambda data, i=index: bridge.graphics.controllers[
    #                         i
    #                     ].clockMemory,
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_memory_free",
    #                     name=f"{name} Memory Free",
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=DATA_GIGABYTES,
    #                     icon="mdi:memory",
    #                     value=lambda data, i=index: round(
    #                         bridge.graphics.controllers[i].memoryFree / 10**3, 2
    #                     ),
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_memory_used_percentage",
    #                     name=f"{name} Memory Used %",
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=PERCENTAGE,
    #                     icon="mdi:memory",
    #                     value=lambda data, i=index: round(
    #                         (
    #                             bridge.graphics.controllers[i].memoryUsed
    #                             / bridge.graphics.controllers[i].memoryTotal
    #                         )
    #                         * 100,
    #                         2,
    #                     ),
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_memory_used",
    #                     name=f"{name} Memory Used",
    #                     entity_registry_enabled_default=False,
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=DATA_GIGABYTES,
    #                     icon="mdi:memory",
    #                     value=lambda data, i=index: round(
    #                         bridge.graphics.controllers[i].memoryUsed / 10**3, 2
    #                     ),
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_fan_speed",
    #                     name=f"{name} Fan Speed",
    #                     entity_registry_enabled_default=False,
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=PERCENTAGE,
    #                     icon="mdi:fan",
    #                     value=lambda data, i=index: bridge.graphics.controllers[
    #                         i
    #                     ].fanSpeed,
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_power_usage",
    #                     name=f"{name} Power Usage",
    #                     entity_registry_enabled_default=False,
    #                     entity_registry_visible_default=True,
    #                     device_class=SensorDeviceClass.POWER,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=POWER_WATT,
    #                     value=lambda data, i=index: bridge.graphics.controllers[
    #                         i
    #                     ].powerDraw,
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_temperature",
    #                     name=f"{name} Temperature",
    #                     entity_registry_enabled_default=False,
    #                     entity_registry_visible_default=True,
    #                     device_class=SensorDeviceClass.TEMPERATURE,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=TEMP_CELSIUS,
    #                     value=lambda data, i=index: bridge.graphics.controllers[
    #                         i
    #                     ].temperatureGpu,
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #             SystemBridgeSensor(
    #                 coordinator,
    #                 SystemBridgeSensorEntityDescription(
    #                     key=f"gpu_{index}_usage_percentage",
    #                     name=f"{name} Usage %",
    #                     entity_registry_visible_default=True,
    #                     state_class=SensorStateClass.MEASUREMENT,
    #                     native_unit_of_measurement=PERCENTAGE,
    #                     icon="mdi:percent",
    #                     value=lambda data, i=index: bridge.graphics.controllers[
    #                         i
    #                     ].utilizationGpu,
    #                 ),
    #                 entry.data[CONF_PORT],
    #             ),
    #         ]

    for index in range(coordinator.data["cpu"]["count"]):
        entities = [
            *entities,
            SystemBridgeSensor(
                coordinator,
                SystemBridgeSensorEntityDescription(
                    key=f"processes_load_cpu_{index}",
                    name=f"Load CPU {index}",
                    entity_registry_enabled_default=False,
                    entity_registry_visible_default=True,
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
