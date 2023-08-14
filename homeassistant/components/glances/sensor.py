"""Support gathering system information of hosts which are running glances."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

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
    Platform,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

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


SENSOR_TYPES = {
    ("fs", "disk_use_percent"): GlancesSensorEntityDescription(
        key="disk_use_percent",
        type="fs",
        name_suffix="used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_use"): GlancesSensorEntityDescription(
        key="disk_use",
        type="fs",
        name_suffix="used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_free"): GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        name_suffix="free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_use_percent"): GlancesSensorEntityDescription(
        key="memory_use_percent",
        type="mem",
        name_suffix="RAM used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_use"): GlancesSensorEntityDescription(
        key="memory_use",
        type="mem",
        name_suffix="RAM used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_free"): GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        name_suffix="RAM free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_use_percent"): GlancesSensorEntityDescription(
        key="swap_use_percent",
        type="memswap",
        name_suffix="Swap used percent",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_use"): GlancesSensorEntityDescription(
        key="swap_use",
        type="memswap",
        name_suffix="Swap used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_free"): GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        name_suffix="Swap free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("load", "processor_load"): GlancesSensorEntityDescription(
        key="processor_load",
        type="load",
        name_suffix="CPU load",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_running"): GlancesSensorEntityDescription(
        key="process_running",
        type="processcount",
        name_suffix="Running",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_total"): GlancesSensorEntityDescription(
        key="process_total",
        type="processcount",
        name_suffix="Total",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_thread"): GlancesSensorEntityDescription(
        key="process_thread",
        type="processcount",
        name_suffix="Thread",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_sleeping"): GlancesSensorEntityDescription(
        key="process_sleeping",
        type="processcount",
        name_suffix="Sleeping",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("cpu", "cpu_use_percent"): GlancesSensorEntityDescription(
        key="cpu_use_percent",
        type="cpu",
        name_suffix="CPU used",
        native_unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "temperature_core"): GlancesSensorEntityDescription(
        key="temperature_core",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "temperature_hdd"): GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "fan_speed"): GlancesSensorEntityDescription(
        key="fan_speed",
        type="sensors",
        name_suffix="Fan speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "battery"): GlancesSensorEntityDescription(
        key="battery",
        type="sensors",
        name_suffix="Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_active"): GlancesSensorEntityDescription(
        key="docker_active",
        type="docker",
        name_suffix="Containers active",
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_cpu_use"): GlancesSensorEntityDescription(
        key="docker_cpu_use",
        type="docker",
        name_suffix="Containers CPU used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_memory_use"): GlancesSensorEntityDescription(
        key="docker_memory_use",
        type="docker",
        name_suffix="Containers RAM used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:docker",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("raid", "available"): GlancesSensorEntityDescription(
        key="available",
        type="raid",
        name_suffix="Raid available",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("raid", "used"): GlancesSensorEntityDescription(
        key="used",
        type="raid",
        name_suffix="Raid used",
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("uptime", "uptime"): GlancesSensorEntityDescription(
        key="uptime",
        type="uptime",
        name_suffix="Uptime",
        icon="mdi:clock-time-eight-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
}


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

    for sensor_type, sensors in coordinator.data.items():
        if sensor_type in ["fs", "sensors", "raid"]:
            for sensor_label, params in sensors.items():
                for param in params:
                    if sensor_description := SENSOR_TYPES.get((sensor_type, param)):
                        _migrate_old_unique_ids(
                            hass,
                            f"{coordinator.host}-{name} {sensor_label} {sensor_description.name_suffix}",
                            f"{sensor_label}-{sensor_description.key}",
                        )
                        entities.append(
                            GlancesSensor(
                                coordinator,
                                name,
                                sensor_label,
                                sensor_description,
                            )
                        )
        elif sensor_type == "uptime":
            if sensor_description := SENSOR_TYPES.get((sensor_type, sensor_type)):
                entities.append(
                    GlancesTimestampSensor(
                        coordinator,
                        name,
                        "",
                        sensor_description,
                    )
                )
        else:
            for sensor in sensors:
                if sensor_description := SENSOR_TYPES.get((sensor_type, sensor)):
                    _migrate_old_unique_ids(
                        hass,
                        f"{coordinator.host}-{name}  {sensor_description.name_suffix}",
                        f"-{sensor_description.key}",
                    )
                    entities.append(
                        GlancesSensor(
                            coordinator,
                            name,
                            "",
                            sensor_description,
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
    def available(self) -> bool:
        """Set sensor unavailable when native value is invalid."""
        if super().available:
            return (
                not self._numeric_state_expected
                or isinstance(value := self.native_value, (int, float))
                or isinstance(value, str)
                and value.isnumeric()
            )
        return False

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the resources."""
        value = self.coordinator.data[self.entity_description.type]

        if isinstance(value, dict):
            if isinstance(value.get(self._sensor_name_prefix), dict):
                return value[self._sensor_name_prefix][self.entity_description.key]
            return value[self.entity_description.key]
        return value


class GlancesTimestampSensor(GlancesSensor):
    """Implementation of a Glances Timestamp sensor."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the resources."""
        value = self.coordinator.data[self.entity_description.type]
        if dt_str := re.search("\\d+:\\d+:\\d+", value):
            dt_value = datetime.strptime(dt_str.group(), "%H:%M:%S")
            days_re = re.match("(\\d+) day", value)
            days = int(days_re.groups()[0]) if days_re is not None else 0
            return utcnow() - timedelta(
                days=days,
                hours=dt_value.hour,
                minutes=dt_value.minute,
                seconds=dt_value.second,
            )
        return None
