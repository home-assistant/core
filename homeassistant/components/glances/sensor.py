"""Support gathering system information of hosts which are running glances."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GlancesDataUpdateCoordinator
from .const import CPU_ICON, DOMAIN


@dataclass
class GlancesSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    type: str
    name_suffix: str


@dataclass
class GlancesSensorEntityDescription(
    SensorEntityDescription, GlancesSensorEntityDescriptionMixin
):
    """Describe Glances sensor entity."""


SENSOR_TYPES: tuple[GlancesSensorEntityDescription, ...] = (
    GlancesSensorEntityDescription(
        key="disk_use_percent",
        type="fs",
        name_suffix="used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="disk_use",
        type="fs",
        name_suffix="used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        name_suffix="free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_use_percent",
        type="mem",
        name_suffix="RAM used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_use",
        type="mem",
        name_suffix="RAM used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        name_suffix="RAM free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_use_percent",
        type="memswap",
        name_suffix="Swap used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_use",
        type="memswap",
        name_suffix="Swap used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        name_suffix="Swap free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="processor_load",
        type="load",
        name_suffix="CPU load",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_running",
        type="processcount",
        name_suffix="Running",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_total",
        type="processcount",
        name_suffix="Total",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_thread",
        type="processcount",
        name_suffix="Thread",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="process_sleeping",
        type="processcount",
        name_suffix="Sleeping",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="cpu_use_percent",
        type="cpu",
        name_suffix="CPU used",
        native_unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="temperature_core",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="fan_speed",
        type="sensors",
        name_suffix="Fan speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="battery",
        type="sensors",
        name_suffix="Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="docker_active",
        type="docker",
        name_suffix="Containers active",
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="docker_cpu_use",
        type="docker",
        name_suffix="Containers CPU used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="docker_memory_use",
        type="docker",
        name_suffix="Containers RAM used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="used",
        type="raid",
        name_suffix="Raid used",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="available",
        type="raid",
        name_suffix="Raid available",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Glances sensors."""

    coordinator: GlancesDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data.get(CONF_NAME)
    entities = []

    @callback
    def _migrate_old_unique_ids(
        hass: HomeAssistant, old_unique_id: str, new_key: str
    ) -> None:
        """Migrate unique IDs to the new format."""
        ent_reg = er.async_get(hass)

        if entity_id := ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, old_unique_id
        ):
            ent_reg.async_update_entity(
                entity_id, new_unique_id=f"{config_entry.entry_id}-{new_key}"
            )

    for description in SENSOR_TYPES:
        if description.type == "fs":
            # fs will provide a list of disks attached
            for disk in coordinator.data[description.type]:
                _migrate_old_unique_ids(
                    hass,
                    f"{coordinator.host}-{name} {disk['mnt_point']} {description.name_suffix}",
                    f"{disk['mnt_point']}-{description.key}",
                )
                entities.append(
                    GlancesSensor(
                        coordinator,
                        name,
                        disk["mnt_point"],
                        description,
                    )
                )
        elif description.type == "sensors":
            # sensors will provide temp for different devices
            for sensor in coordinator.data[description.type]:
                if sensor["type"] == description.key:
                    _migrate_old_unique_ids(
                        hass,
                        f"{coordinator.host}-{name} {sensor['label']} {description.name_suffix}",
                        f"{sensor['label']}-{description.key}",
                    )
                    entities.append(
                        GlancesSensor(
                            coordinator,
                            name,
                            sensor["label"],
                            description,
                        )
                    )
        elif description.type == "raid":
            for raid_device in coordinator.data[description.type]:
                _migrate_old_unique_ids(
                    hass,
                    f"{coordinator.host}-{name} {raid_device} {description.name_suffix}",
                    f"{raid_device}-{description.key}",
                )
                entities.append(
                    GlancesSensor(coordinator, name, raid_device, description)
                )
        elif coordinator.data[description.type]:
            _migrate_old_unique_ids(
                hass,
                f"{coordinator.host}-{name}  {description.name_suffix}",
                f"-{description.key}",
            )
            entities.append(
                GlancesSensor(
                    coordinator,
                    name,
                    "",
                    description,
                )
            )

    async_add_entities(entities)


class GlancesSensor(CoordinatorEntity[GlancesDataUpdateCoordinator], SensorEntity):
    """Implementation of a Glances sensor."""

    entity_description: GlancesSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GlancesDataUpdateCoordinator,
        name: str | None,
        sensor_name_prefix: str,
        description: GlancesSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_name_prefix = sensor_name_prefix
        self.entity_description = description
        self._attr_name = f"{sensor_name_prefix} {description.name_suffix}".strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Glances",
            name=name or coordinator.host,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{sensor_name_prefix}-{description.key}"

    @property
    def native_value(self) -> StateType:  # noqa: C901
        """Return the state of the resources."""
        if (value := self.coordinator.data) is None:
            return None
        state: StateType = None
        if self.entity_description.type == "fs":
            for var in value["fs"]:
                if var["mnt_point"] == self._sensor_name_prefix:
                    disk = var
                    break
            if self.entity_description.key == "disk_free":
                try:
                    state = round(disk["free"] / 1024**3, 1)
                except KeyError:
                    state = round(
                        (disk["size"] - disk["used"]) / 1024**3,
                        1,
                    )
            elif self.entity_description.key == "disk_use":
                state = round(disk["used"] / 1024**3, 1)
            elif self.entity_description.key == "disk_use_percent":
                state = disk["percent"]
        elif self.entity_description.key == "battery":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "battery"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    state = sensor["value"]
        elif self.entity_description.key == "fan_speed":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "fan_speed"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    state = sensor["value"]
        elif self.entity_description.key == "temperature_core":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "temperature_core"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    state = sensor["value"]
        elif self.entity_description.key == "temperature_hdd":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "temperature_hdd"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    state = sensor["value"]
        elif self.entity_description.key == "memory_use_percent":
            state = value["mem"]["percent"]
        elif self.entity_description.key == "memory_use":
            state = round(value["mem"]["used"] / 1024**2, 1)
        elif self.entity_description.key == "memory_free":
            state = round(value["mem"]["free"] / 1024**2, 1)
        elif self.entity_description.key == "swap_use_percent":
            state = value["memswap"]["percent"]
        elif self.entity_description.key == "swap_use":
            state = round(value["memswap"]["used"] / 1024**3, 1)
        elif self.entity_description.key == "swap_free":
            state = round(value["memswap"]["free"] / 1024**3, 1)
        elif self.entity_description.key == "processor_load":
            # Windows systems don't provide load details
            try:
                state = value["load"]["min15"]
            except KeyError:
                state = value["cpu"]["total"]
        elif self.entity_description.key == "process_running":
            state = value["processcount"]["running"]
        elif self.entity_description.key == "process_total":
            state = value["processcount"]["total"]
        elif self.entity_description.key == "process_thread":
            state = value["processcount"]["thread"]
        elif self.entity_description.key == "process_sleeping":
            state = value["processcount"]["sleeping"]
        elif self.entity_description.key == "cpu_use_percent":
            state = value["quicklook"]["cpu"]
        elif self.entity_description.key == "docker_active":
            count = 0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        count += 1
                state = count
            except KeyError:
                state = count
        elif self.entity_description.key == "docker_cpu_use":
            cpu_use = 0.0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        cpu_use += container["cpu"]["total"]
                    state = round(cpu_use, 1)
            except KeyError:
                state = STATE_UNAVAILABLE
        elif self.entity_description.key == "docker_memory_use":
            mem_use = 0.0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        mem_use += container["memory"]["usage"]
                    state = round(mem_use / 1024**2, 1)
            except KeyError:
                state = STATE_UNAVAILABLE
        elif self.entity_description.type == "raid":
            for raid_device, raid in value["raid"].items():
                if raid_device == self._sensor_name_prefix:
                    state = raid[self.entity_description.key]

        return state
