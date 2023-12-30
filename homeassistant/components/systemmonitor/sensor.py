"""Support for monitoring the local system."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache, lru_cache
import logging
import sys
from typing import Any, Literal

from psutil._common import sdiskusage, sswap
from psutil._pslinux import svmem
import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_RESOURCES,
    CONF_TYPE,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_PROCESS, DOMAIN, NETWORK_TYPES
from .coordinator import (
    MonitorCoordinator,
    SystemMonitorBootTimeCoordinator,
    SystemMonitorCPUtempCoordinator,
    SystemMonitorDiskCoordinator,
    SystemMonitorLoadCoordinator,
    SystemMonitorMemoryCoordinator,
    SystemMonitorNetAddrCoordinator,
    SystemMonitorNetIOCoordinator,
    SystemMonitorNetThroughputCoordinator,
    SystemMonitorProcessCoordinator,
    SystemMonitorProcessorCoordinator,
    SystemMonitorSwapCoordinator,
)
from .util import get_all_disk_mounts, get_all_network_interfaces, read_cpu_temperature

_LOGGER = logging.getLogger(__name__)

CONF_ARG = "arg"


SENSOR_TYPE_NAME = 0
SENSOR_TYPE_UOM = 1
SENSOR_TYPE_ICON = 2
SENSOR_TYPE_DEVICE_CLASS = 3
SENSOR_TYPE_MANDATORY_ARG = 4

SIGNAL_SYSTEMMONITOR_UPDATE = "systemmonitor_update"


@lru_cache
def get_cpu_icon() -> Literal["mdi:cpu-64-bit", "mdi:cpu-32-bit"]:
    """Return cpu icon."""
    if sys.maxsize > 2**32:
        return "mdi:cpu-64-bit"
    return "mdi:cpu-32-bit"


@dataclass(frozen=True)
class SysMonitorSensorEntityDescription(SensorEntityDescription):
    """Description for System Monitor sensor entities."""

    coordinator: type[MonitorCoordinator]
    mandatory_arg: bool = False
    placeholder: str | None = None
    value_disk: Callable[[sdiskusage], float] | None = None
    value_swap: Callable[[sswap], float] | None = None
    value_memory: Callable[[svmem], float] | None = None
    value_net_io: Callable[[int], float] | None = None
    value_net_throughput: Callable[[float], float] | None = None
    value_net_addr: Callable[[str], str] | None = None
    value_load: Callable[[tuple[float, float, float]], float] | None = None
    value_processor: Callable[[float], float] | None = None
    value_boot_time: Callable[[datetime], datetime] | None = None
    value_process: Callable[[bool], str] | None = None
    value_cpu_temp: Callable[[float], float] | None = None


SENSOR_TYPES: dict[str, SysMonitorSensorEntityDescription] = {
    "disk_free": SysMonitorSensorEntityDescription(
        key="disk_free",
        translation_key="disk_free",
        placeholder="mount_point",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorDiskCoordinator,
        value_disk=lambda data: round(data.free / 1024**3, 1),
    ),
    "disk_use": SysMonitorSensorEntityDescription(
        key="disk_use",
        translation_key="disk_use",
        placeholder="mount_point",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorDiskCoordinator,
        value_disk=lambda data: round(data.used / 1024**3, 1),
    ),
    "disk_use_percent": SysMonitorSensorEntityDescription(
        key="disk_use_percent",
        translation_key="disk_use_percent",
        placeholder="mount_point",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorDiskCoordinator,
        value_disk=lambda data: data.percent,
    ),
    "ipv4_address": SysMonitorSensorEntityDescription(
        key="ipv4_address",
        translation_key="ipv4_address",
        placeholder="ip_address",
        icon="mdi:ip-network",
        mandatory_arg=True,
        coordinator=SystemMonitorNetAddrCoordinator,
        value_net_addr=lambda data: data,
    ),
    "ipv6_address": SysMonitorSensorEntityDescription(
        key="ipv6_address",
        translation_key="ipv6_address",
        placeholder="ip_address",
        icon="mdi:ip-network",
        mandatory_arg=True,
        coordinator=SystemMonitorNetAddrCoordinator,
        value_net_addr=lambda data: data,
    ),
    "last_boot": SysMonitorSensorEntityDescription(
        key="last_boot",
        translation_key="last_boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        coordinator=SystemMonitorBootTimeCoordinator,
        value_boot_time=lambda data: data,
    ),
    "load_15m": SysMonitorSensorEntityDescription(
        key="load_15m",
        translation_key="load_15m",
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorLoadCoordinator,
        value_load=lambda data: round(data[2], 2),
    ),
    "load_1m": SysMonitorSensorEntityDescription(
        key="load_1m",
        translation_key="load_1m",
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorLoadCoordinator,
        value_load=lambda data: round(data[0], 2),
    ),
    "load_5m": SysMonitorSensorEntityDescription(
        key="load_5m",
        translation_key="load_5m",
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorLoadCoordinator,
        value_load=lambda data: round(data[1], 2),
    ),
    "memory_free": SysMonitorSensorEntityDescription(
        key="memory_free",
        translation_key="memory_free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorMemoryCoordinator,
        value_memory=lambda data: round(data.available / 1024**2, 1),
    ),
    "memory_use": SysMonitorSensorEntityDescription(
        key="memory_use",
        translation_key="memory_use",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorMemoryCoordinator,
        value_memory=lambda data: round((data.total - data.available) / 1024**2, 1),
    ),
    "memory_use_percent": SysMonitorSensorEntityDescription(
        key="memory_use_percent",
        translation_key="memory_use_percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorMemoryCoordinator,
        value_memory=lambda data: data.percent,
    ),
    "network_in": SysMonitorSensorEntityDescription(
        key="network_in",
        translation_key="network_in",
        placeholder="interface",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:server-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        coordinator=SystemMonitorNetIOCoordinator,
        value_net_io=lambda data: round(data / 1024**2, 1),
    ),
    "network_out": SysMonitorSensorEntityDescription(
        key="network_out",
        translation_key="network_out",
        placeholder="interface",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:server-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        coordinator=SystemMonitorNetIOCoordinator,
        value_net_io=lambda data: round(data / 1024**2, 1),
    ),
    "packets_in": SysMonitorSensorEntityDescription(
        key="packets_in",
        translation_key="packets_in",
        placeholder="interface",
        icon="mdi:server-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        coordinator=SystemMonitorNetIOCoordinator,
        value_net_io=lambda data: data,
    ),
    "packets_out": SysMonitorSensorEntityDescription(
        key="packets_out",
        translation_key="packets_out",
        placeholder="interface",
        icon="mdi:server-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        coordinator=SystemMonitorNetIOCoordinator,
        value_net_io=lambda data: data,
    ),
    "throughput_network_in": SysMonitorSensorEntityDescription(
        key="throughput_network_in",
        translation_key="throughput_network_in",
        placeholder="interface",
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        mandatory_arg=True,
        coordinator=SystemMonitorNetThroughputCoordinator,
        value_net_throughput=lambda data: data,
    ),
    "throughput_network_out": SysMonitorSensorEntityDescription(
        key="throughput_network_out",
        translation_key="throughput_network_out",
        placeholder="interface",
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        mandatory_arg=True,
        coordinator=SystemMonitorNetThroughputCoordinator,
        value_net_throughput=lambda data: data,
    ),
    "process": SysMonitorSensorEntityDescription(
        key="process",
        translation_key="process",
        placeholder="process",
        icon=get_cpu_icon(),
        mandatory_arg=True,
        coordinator=SystemMonitorProcessCoordinator,
        value_process=lambda data: STATE_ON if data is True else STATE_OFF,
    ),
    "processor_use": SysMonitorSensorEntityDescription(
        key="processor_use",
        translation_key="processor_use",
        native_unit_of_measurement=PERCENTAGE,
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorProcessorCoordinator,
        value_processor=lambda data: data,
    ),
    "processor_temperature": SysMonitorSensorEntityDescription(
        key="processor_temperature",
        translation_key="processor_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorCPUtempCoordinator,
        value_cpu_temp=lambda data: data,
    ),
    "swap_free": SysMonitorSensorEntityDescription(
        key="swap_free",
        translation_key="swap_free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorSwapCoordinator,
        value_swap=lambda data: round(data.free / 1024**2, 1),
    ),
    "swap_use": SysMonitorSensorEntityDescription(
        key="swap_use",
        translation_key="swap_use",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorSwapCoordinator,
        value_swap=lambda data: round(data.used / 1024**2, 1),
    ),
    "swap_use_percent": SysMonitorSensorEntityDescription(
        key="swap_use_percent",
        translation_key="swap_use_percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
        coordinator=SystemMonitorSwapCoordinator,
        value_swap=lambda data: data.percent,
    ),
}


def check_required_arg(value: Any) -> Any:
    """Validate that the required "arg" for the sensor types that need it are set."""
    for sensor in value:
        sensor_type = sensor[CONF_TYPE]
        sensor_arg = sensor.get(CONF_ARG)

        if sensor_arg is None and SENSOR_TYPES[sensor_type].mandatory_arg:
            raise vol.RequiredFieldInvalid(
                f"Mandatory 'arg' is missing for sensor type '{sensor_type}'."
            )

    return value


def check_legacy_resource(resource: str, resources: set[str]) -> bool:
    """Return True if legacy resource was configured."""
    # This function to check legacy resources can be removed
    # once we are removing the import from YAML
    if resource in resources:
        _LOGGER.debug("Checking %s in %s returns True", resource, ", ".join(resources))
        return True
    _LOGGER.debug("Checking %s in %s returns False", resource, ", ".join(resources))
    return False


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RESOURCES, default={CONF_TYPE: "disk_use"}): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
                        vol.Optional(CONF_ARG): cv.string,
                    }
                )
            ],
            check_required_arg,
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the system monitor sensors."""
    processes = [
        resource[CONF_ARG]
        for resource in config[CONF_RESOURCES]
        if resource[CONF_TYPE] == "process"
    ]
    legacy_config: list[dict[str, str]] = config[CONF_RESOURCES]
    resources = []
    for resource_conf in legacy_config:
        if (_type := resource_conf[CONF_TYPE]).startswith("disk_"):
            if (arg := resource_conf.get(CONF_ARG)) is None:
                resources.append(f"{_type}_/")
                continue
            resources.append(f"{_type}_{arg}")
            continue
        resources.append(f"{_type}_{resource_conf.get(CONF_ARG, '')}")
    _LOGGER.debug(
        "Importing config with processes: %s, resources: %s", processes, resources
    )

    # With removal of the import also cleanup legacy_resources logic in setup_entry
    # Also cleanup entry.options["resources"] which is only imported for legacy reasons

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"processes": processes, "legacy_resources": resources},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up System Montor sensors based on a config entry."""
    entities = []
    legacy_resources: set[str] = set(entry.options.get("resources", []))
    loaded_resources: set[str] = set()
    disk_arguments = await hass.async_add_executor_job(get_all_disk_mounts)
    network_arguments = await hass.async_add_executor_job(get_all_network_interfaces)
    cpu_temperature = await hass.async_add_executor_job(read_cpu_temperature)

    _LOGGER.debug("Setup from options %s", entry.options)

    for _type, sensor_description in SENSOR_TYPES.items():
        if _type.startswith("disk_"):
            for argument in disk_arguments:
                is_enabled = check_legacy_resource(
                    f"{_type}_{argument}", legacy_resources
                )
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        hass,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        is_enabled,
                    )
                )
            continue

        if _type in NETWORK_TYPES:
            for argument in network_arguments:
                is_enabled = check_legacy_resource(
                    f"{_type}_{argument}", legacy_resources
                )
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        hass,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        is_enabled,
                    )
                )
            continue

        # Verify if we can retrieve CPU / processor temperatures.
        # If not, do not create the entity and add a warning to the log
        if _type == "processor_temperature" and cpu_temperature is None:
            _LOGGER.warning("Cannot read CPU / processor temperature information")
            continue

        if _type == "process":
            _entry: dict[str, list] = entry.options.get(SENSOR_DOMAIN, {})
            for argument in _entry.get(CONF_PROCESS, []):
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        hass,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        True,
                    )
                )
            continue

        is_enabled = check_legacy_resource(f"{_type}_", legacy_resources)
        loaded_resources.add(f"{_type}_")
        entities.append(
            SystemMonitorSensor(
                hass,
                sensor_description,
                entry.entry_id,
                "",
                is_enabled,
            )
        )

    # Ensure legacy imported disk_* resources are loaded if they are not part
    # of mount points automatically discovered
    for resource in legacy_resources:
        if resource.startswith("disk_"):
            check_resource = slugify(resource)
            _LOGGER.debug(
                "Check resource %s already loaded in %s",
                check_resource,
                loaded_resources,
            )
            if check_resource not in loaded_resources:
                split_index = resource.rfind("_")
                _type = resource[:split_index]
                argument = resource[split_index + 1 :]
                _LOGGER.debug("Loading legacy %s with argument %s", _type, argument)
                entities.append(
                    SystemMonitorSensor(
                        hass,
                        SENSOR_TYPES[_type],
                        entry.entry_id,
                        argument,
                        True,
                    )
                )

    async_add_entities(entities)


class SystemMonitorSensor(CoordinatorEntity[MonitorCoordinator], SensorEntity):
    """Implementation of a system monitor sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: SysMonitorSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        sensor_description: SysMonitorSensorEntityDescription,
        entry_id: str,
        argument: str = "",
        legacy_enabled: bool = False,
    ) -> None:
        """Initialize the sensor."""
        coordinator: MonitorCoordinator = sensor_description.coordinator(
            hass, sensor_description.key, argument
        )
        super().__init__(coordinator)
        self.entity_description = sensor_description
        if self.entity_description.placeholder:
            self._attr_translation_placeholders = {
                self.entity_description.placeholder: argument
            }
        self._attr_unique_id: str = slugify(f"{sensor_description.key}_{argument}")
        self._attr_entity_registry_enabled_default = legacy_enabled
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="System Monitor",
            name="System Monitor",
        )

    def native_value(self) -> str | float | int | datetime | None:
        """Return the state."""
        data = self.coordinator.data
        if value_disk := self.entity_description.value_disk:
            return value_disk(data)
        if value_swap := self.entity_description.value_swap:
            return value_swap(data)
        if value_memory := self.entity_description.value_memory:
            return value_memory(data)
        if value_net_io := self.entity_description.value_net_io:
            return value_net_io(data)
        if value_net_throughput := self.entity_description.value_net_throughput:
            return value_net_throughput(data)
        if value_net_addr := self.entity_description.value_net_addr:
            return value_net_addr(data)
        if value_load := self.entity_description.value_load:
            return value_load(data)
        if value_processor := self.entity_description.value_processor:
            return value_processor(data)
        if value_boot_time := self.entity_description.value_boot_time:
            return value_boot_time(data)
        if value_process := self.entity_description.value_process:
            return value_process(data)
        if value_cpu_temp := self.entity_description.value_cpu_temp:
            return value_cpu_temp(data)
        return None
