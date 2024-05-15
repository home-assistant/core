"""Support for monitoring the local system."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import ipaddress
import logging
import socket
import sys
import time
from typing import Any, Literal

from psutil import NoSuchProcess
import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import SystemMonitorConfigEntry
from .const import CONF_PROCESS, DOMAIN, NET_IO_TYPES
from .coordinator import SystemMonitorCoordinator
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


def get_process(entity: SystemMonitorSensor) -> str:
    """Return process."""
    state = STATE_OFF
    for proc in entity.coordinator.data.processes:
        try:
            _LOGGER.debug("process %s for argument %s", proc.name(), entity.argument)
            if entity.argument == proc.name():
                state = STATE_ON
                break
        except NoSuchProcess as err:
            _LOGGER.warning(
                "Failed to load process with ID: %s, old name: %s",
                err.pid,
                err.name,
            )
    return state


def get_network(entity: SystemMonitorSensor) -> float | None:
    """Return network in and out."""
    counters = entity.coordinator.data.io_counters
    if entity.argument in counters:
        counter = counters[entity.argument][IO_COUNTER[entity.entity_description.key]]
        return round(counter / 1024**2, 1)
    return None


def get_packets(entity: SystemMonitorSensor) -> float | None:
    """Return packets in and out."""
    counters = entity.coordinator.data.io_counters
    if entity.argument in counters:
        return counters[entity.argument][IO_COUNTER[entity.entity_description.key]]
    return None


def get_throughput(entity: SystemMonitorSensor) -> float | None:
    """Return network throughput in and out."""
    counters = entity.coordinator.data.io_counters
    state = None
    if entity.argument in counters:
        counter = counters[entity.argument][IO_COUNTER[entity.entity_description.key]]
        now = time.monotonic()
        if (
            (value := entity.value)
            and (update_time := entity.update_time)
            and value < counter
        ):
            state = round(
                (counter - value) / 1000**2 / (now - update_time),
                3,
            )
        entity.update_time = now
        entity.value = counter
    return state


def get_ip_address(
    entity: SystemMonitorSensor,
) -> str | None:
    """Return network ip address."""
    addresses = entity.coordinator.data.addresses
    if entity.argument in addresses:
        for addr in addresses[entity.argument]:
            if addr.family == IF_ADDRS_FAMILY[entity.entity_description.key]:
                address = ipaddress.ip_address(addr.address)
                if address.version == 6 and (
                    address.is_link_local or address.is_loopback
                ):
                    continue
                return addr.address
    return None


@dataclass(frozen=True, kw_only=True)
class SysMonitorSensorEntityDescription(SensorEntityDescription):
    """Describes System Monitor sensor entities."""

    value_fn: Callable[[SystemMonitorSensor], StateType | datetime]
    add_to_update: Callable[[SystemMonitorSensor], tuple[str, str]]
    none_is_unavailable: bool = False
    mandatory_arg: bool = False
    placeholder: str | None = None


SENSOR_TYPES: dict[str, SysMonitorSensorEntityDescription] = {
    "disk_free": SysMonitorSensorEntityDescription(
        key="disk_free",
        translation_key="disk_free",
        placeholder="mount_point",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(
            entity.coordinator.data.disk_usage[entity.argument].free / 1024**3, 1
        )
        if entity.argument in entity.coordinator.data.disk_usage
        else None,
        none_is_unavailable=True,
        add_to_update=lambda entity: ("disks", entity.argument),
    ),
    "disk_use": SysMonitorSensorEntityDescription(
        key="disk_use",
        translation_key="disk_use",
        placeholder="mount_point",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(
            entity.coordinator.data.disk_usage[entity.argument].used / 1024**3, 1
        )
        if entity.argument in entity.coordinator.data.disk_usage
        else None,
        none_is_unavailable=True,
        add_to_update=lambda entity: ("disks", entity.argument),
    ),
    "disk_use_percent": SysMonitorSensorEntityDescription(
        key="disk_use_percent",
        translation_key="disk_use_percent",
        placeholder="mount_point",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.coordinator.data.disk_usage[
            entity.argument
        ].percent
        if entity.argument in entity.coordinator.data.disk_usage
        else None,
        none_is_unavailable=True,
        add_to_update=lambda entity: ("disks", entity.argument),
    ),
    "ipv4_address": SysMonitorSensorEntityDescription(
        key="ipv4_address",
        translation_key="ipv4_address",
        placeholder="ip_address",
        mandatory_arg=True,
        value_fn=get_ip_address,
        add_to_update=lambda entity: ("addresses", ""),
    ),
    "ipv6_address": SysMonitorSensorEntityDescription(
        key="ipv6_address",
        translation_key="ipv6_address",
        placeholder="ip_address",
        mandatory_arg=True,
        value_fn=get_ip_address,
        add_to_update=lambda entity: ("addresses", ""),
    ),
    "last_boot": SysMonitorSensorEntityDescription(
        key="last_boot",
        translation_key="last_boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda entity: entity.coordinator.data.boot_time,
        add_to_update=lambda entity: ("boot", ""),
    ),
    "load_15m": SysMonitorSensorEntityDescription(
        key="load_15m",
        translation_key="load_15m",
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(entity.coordinator.data.load[2], 2),
        add_to_update=lambda entity: ("load", ""),
    ),
    "load_1m": SysMonitorSensorEntityDescription(
        key="load_1m",
        translation_key="load_1m",
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(entity.coordinator.data.load[0], 2),
        add_to_update=lambda entity: ("load", ""),
    ),
    "load_5m": SysMonitorSensorEntityDescription(
        key="load_5m",
        translation_key="load_5m",
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(entity.coordinator.data.load[1], 2),
        add_to_update=lambda entity: ("load", ""),
    ),
    "memory_free": SysMonitorSensorEntityDescription(
        key="memory_free",
        translation_key="memory_free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(
            entity.coordinator.data.memory.available / 1024**2, 1
        ),
        add_to_update=lambda entity: ("memory", ""),
    ),
    "memory_use": SysMonitorSensorEntityDescription(
        key="memory_use",
        translation_key="memory_use",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(
            (
                entity.coordinator.data.memory.total
                - entity.coordinator.data.memory.available
            )
            / 1024**2,
            1,
        ),
        add_to_update=lambda entity: ("memory", ""),
    ),
    "memory_use_percent": SysMonitorSensorEntityDescription(
        key="memory_use_percent",
        translation_key="memory_use_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.coordinator.data.memory.percent,
        add_to_update=lambda entity: ("memory", ""),
    ),
    "network_in": SysMonitorSensorEntityDescription(
        key="network_in",
        translation_key="network_in",
        placeholder="interface",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        value_fn=get_network,
        add_to_update=lambda entity: ("io_counters", ""),
    ),
    "network_out": SysMonitorSensorEntityDescription(
        key="network_out",
        translation_key="network_out",
        placeholder="interface",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        value_fn=get_network,
        add_to_update=lambda entity: ("io_counters", ""),
    ),
    "packets_in": SysMonitorSensorEntityDescription(
        key="packets_in",
        translation_key="packets_in",
        placeholder="interface",
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        value_fn=get_packets,
        add_to_update=lambda entity: ("io_counters", ""),
    ),
    "packets_out": SysMonitorSensorEntityDescription(
        key="packets_out",
        translation_key="packets_out",
        placeholder="interface",
        state_class=SensorStateClass.TOTAL_INCREASING,
        mandatory_arg=True,
        value_fn=get_packets,
        add_to_update=lambda entity: ("io_counters", ""),
    ),
    "throughput_network_in": SysMonitorSensorEntityDescription(
        key="throughput_network_in",
        translation_key="throughput_network_in",
        placeholder="interface",
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        mandatory_arg=True,
        value_fn=get_throughput,
        add_to_update=lambda entity: ("io_counters", ""),
    ),
    "throughput_network_out": SysMonitorSensorEntityDescription(
        key="throughput_network_out",
        translation_key="throughput_network_out",
        placeholder="interface",
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        mandatory_arg=True,
        value_fn=get_throughput,
        add_to_update=lambda entity: ("io_counters", ""),
    ),
    "process": SysMonitorSensorEntityDescription(
        key="process",
        translation_key="process",
        placeholder="process",
        icon=get_cpu_icon(),
        mandatory_arg=True,
        value_fn=get_process,
        add_to_update=lambda entity: ("processes", ""),
    ),
    "processor_use": SysMonitorSensorEntityDescription(
        key="processor_use",
        translation_key="processor_use",
        native_unit_of_measurement=PERCENTAGE,
        icon=get_cpu_icon(),
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: (
            round(entity.coordinator.data.cpu_percent)
            if entity.coordinator.data.cpu_percent
            else None
        ),
        add_to_update=lambda entity: ("cpu_percent", ""),
    ),
    "processor_temperature": SysMonitorSensorEntityDescription(
        key="processor_temperature",
        translation_key="processor_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: read_cpu_temperature(
            entity.coordinator.data.temperatures
        ),
        none_is_unavailable=True,
        add_to_update=lambda entity: ("temperatures", ""),
    ),
    "swap_free": SysMonitorSensorEntityDescription(
        key="swap_free",
        translation_key="swap_free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(entity.coordinator.data.swap.free / 1024**2, 1),
        add_to_update=lambda entity: ("swap", ""),
    ),
    "swap_use": SysMonitorSensorEntityDescription(
        key="swap_use",
        translation_key="swap_use",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: round(entity.coordinator.data.swap.used / 1024**2, 1),
        add_to_update=lambda entity: ("swap", ""),
    ),
    "swap_use_percent": SysMonitorSensorEntityDescription(
        key="swap_use_percent",
        translation_key="swap_use_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.coordinator.data.swap.percent,
        add_to_update=lambda entity: ("swap", ""),
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

IO_COUNTER = {
    "network_out": 0,
    "network_in": 1,
    "packets_out": 2,
    "packets_in": 3,
    "throughput_network_out": 0,
    "throughput_network_in": 1,
}
IF_ADDRS_FAMILY = {"ipv4_address": socket.AF_INET, "ipv6_address": socket.AF_INET6}


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
    hass: HomeAssistant,
    entry: SystemMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up System Montor sensors based on a config entry."""
    entities: list[SystemMonitorSensor] = []
    legacy_resources: set[str] = set(entry.options.get("resources", []))
    loaded_resources: set[str] = set()
    coordinator = entry.runtime_data.coordinator
    psutil_wrapper = entry.runtime_data.psutil_wrapper
    sensor_data = coordinator.data

    def get_arguments() -> dict[str, Any]:
        """Return startup information."""
        return {
            "disk_arguments": get_all_disk_mounts(hass, psutil_wrapper),
            "network_arguments": get_all_network_interfaces(hass, psutil_wrapper),
        }

    cpu_temperature: float | None = None
    with contextlib.suppress(AttributeError):
        cpu_temperature = read_cpu_temperature(sensor_data.temperatures)

    startup_arguments = await hass.async_add_executor_job(get_arguments)
    startup_arguments["cpu_temperature"] = cpu_temperature

    _LOGGER.debug("Setup from options %s", entry.options)

    for _type, sensor_description in SENSOR_TYPES.items():
        if _type.startswith("disk_"):
            for argument in startup_arguments["disk_arguments"]:
                is_enabled = check_legacy_resource(
                    f"{_type}_{argument}", legacy_resources
                )
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        coordinator,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        is_enabled,
                    )
                )
            continue

        if _type.startswith("ipv"):
            for argument in startup_arguments["network_arguments"]:
                is_enabled = check_legacy_resource(
                    f"{_type}_{argument}", legacy_resources
                )
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        coordinator,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        is_enabled,
                    )
                )
            continue

        if _type == "last_boot":
            argument = ""
            is_enabled = check_legacy_resource(f"{_type}_{argument}", legacy_resources)
            loaded_resources.add(slugify(f"{_type}_{argument}"))
            entities.append(
                SystemMonitorSensor(
                    coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
                    is_enabled,
                )
            )
            continue

        if _type.startswith("load_"):
            argument = ""
            is_enabled = check_legacy_resource(f"{_type}_{argument}", legacy_resources)
            loaded_resources.add(slugify(f"{_type}_{argument}"))
            entities.append(
                SystemMonitorSensor(
                    coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
                    is_enabled,
                )
            )
            continue

        if _type.startswith("memory_"):
            argument = ""
            is_enabled = check_legacy_resource(f"{_type}_{argument}", legacy_resources)
            loaded_resources.add(slugify(f"{_type}_{argument}"))
            entities.append(
                SystemMonitorSensor(
                    coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
                    is_enabled,
                )
            )

        if _type in NET_IO_TYPES:
            for argument in startup_arguments["network_arguments"]:
                is_enabled = check_legacy_resource(
                    f"{_type}_{argument}", legacy_resources
                )
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        coordinator,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        is_enabled,
                    )
                )
            continue

        if _type == "process":
            _entry = entry.options.get(SENSOR_DOMAIN, {})
            for argument in _entry.get(CONF_PROCESS, []):
                loaded_resources.add(slugify(f"{_type}_{argument}"))
                entities.append(
                    SystemMonitorSensor(
                        coordinator,
                        sensor_description,
                        entry.entry_id,
                        argument,
                        True,
                    )
                )
                async_create_issue(
                    hass,
                    DOMAIN,
                    "process_sensor",
                    breaks_in_ha_version="2024.9.0",
                    is_fixable=True,
                    is_persistent=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="process_sensor",
                    data={
                        "entry_id": entry.entry_id,
                        "processes": _entry[CONF_PROCESS],
                    },
                )
            continue

        if _type == "processor_use":
            argument = ""
            is_enabled = check_legacy_resource(f"{_type}_{argument}", legacy_resources)
            loaded_resources.add(slugify(f"{_type}_{argument}"))
            entities.append(
                SystemMonitorSensor(
                    coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
                    is_enabled,
                )
            )
            continue

        if _type == "processor_temperature":
            if not startup_arguments["cpu_temperature"]:
                # Don't load processor temperature sensor if we can't read it.
                continue
            argument = ""
            is_enabled = check_legacy_resource(f"{_type}_{argument}", legacy_resources)
            loaded_resources.add(slugify(f"{_type}_{argument}"))
            entities.append(
                SystemMonitorSensor(
                    coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
                    is_enabled,
                )
            )
            continue

        if _type.startswith("swap_"):
            argument = ""
            is_enabled = check_legacy_resource(f"{_type}_{argument}", legacy_resources)
            loaded_resources.add(slugify(f"{_type}_{argument}"))
            entities.append(
                SystemMonitorSensor(
                    coordinator,
                    sensor_description,
                    entry.entry_id,
                    argument,
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
                loaded_resources.add(check_resource)
                split_index = resource.rfind("_")
                _type = resource[:split_index]
                argument = resource[split_index + 1 :]
                _LOGGER.debug("Loading legacy %s with argument %s", _type, argument)
                entities.append(
                    SystemMonitorSensor(
                        coordinator,
                        SENSOR_TYPES[_type],
                        entry.entry_id,
                        argument,
                        True,
                    )
                )

    @callback
    def clean_obsolete_entities() -> None:
        """Remove entities which are disabled and not supported from setup."""
        entity_registry = er.async_get(hass)
        entities = entity_registry.entities.get_entries_for_config_entry_id(
            entry.entry_id
        )
        for entity in entities:
            if (
                entity.unique_id not in loaded_resources
                and entity.disabled is True
                and (
                    entity_id := entity_registry.async_get_entity_id(
                        SENSOR_DOMAIN, DOMAIN, entity.unique_id
                    )
                )
            ):
                entity_registry.async_remove(entity_id)

    clean_obsolete_entities()

    async_add_entities(entities)


class SystemMonitorSensor(CoordinatorEntity[SystemMonitorCoordinator], SensorEntity):
    """Implementation of a system monitor sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: SysMonitorSensorEntityDescription
    argument: str

    def __init__(
        self,
        coordinator: SystemMonitorCoordinator,
        sensor_description: SysMonitorSensorEntityDescription,
        entry_id: str,
        argument: str,
        legacy_enabled: bool = False,
    ) -> None:
        """Initialize the sensor."""
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
        self.argument = argument
        self.value: int | None = None
        self.update_time: float | None = None
        self._attr_native_value = self.entity_description.value_fn(self)

    async def async_added_to_hass(self) -> None:
        """When added to hass."""
        self.coordinator.update_subscribers[
            self.entity_description.add_to_update(self)
        ].add(self.entity_id)
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """When removed from hass."""
        self.coordinator.update_subscribers[
            self.entity_description.add_to_update(self)
        ].remove(self.entity_id)
        return await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Set the native value here so we can use it in available property
        # without having to recalculate it
        self._attr_native_value = self.entity_description.value_fn(self)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.entity_description.none_is_unavailable:
            return (
                self.coordinator.last_update_success is True
                and self.native_value is not None
            )
        return super().available
