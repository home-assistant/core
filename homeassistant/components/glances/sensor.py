"""Support gathering system information of hosts which are running Glances."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CPU_ICON, DOMAIN
from .coordinator import GlancesConfigEntry, GlancesDataUpdateCoordinator

DYNAMIC_TYPES = {"fs", "diskio", "sensors", "raid", "gpu", "network"}


@dataclass(frozen=True, kw_only=True)
class GlancesSensorEntityDescription(SensorEntityDescription):
    """Describe Glances sensor entity."""

    type: str


SENSOR_TYPES = {
    ("fs", "disk_use_percent"): GlancesSensorEntityDescription(
        key="disk_use_percent",
        type="fs",
        translation_key="disk_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_use"): GlancesSensorEntityDescription(
        key="disk_use",
        type="fs",
        translation_key="disk_used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_size"): GlancesSensorEntityDescription(
        key="disk_size",
        type="fs",
        translation_key="disk_size",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("fs", "disk_free"): GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        translation_key="disk_free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("diskio", "read"): GlancesSensorEntityDescription(
        key="read",
        type="diskio",
        translation_key="diskio_read",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("diskio", "write"): GlancesSensorEntityDescription(
        key="write",
        type="diskio",
        translation_key="diskio_write",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_use_percent"): GlancesSensorEntityDescription(
        key="memory_use_percent",
        type="mem",
        translation_key="memory_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_use"): GlancesSensorEntityDescription(
        key="memory_use",
        type="mem",
        translation_key="memory_use",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("mem", "memory_free"): GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        translation_key="memory_free",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_use_percent"): GlancesSensorEntityDescription(
        key="swap_use_percent",
        type="memswap",
        translation_key="swap_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_use"): GlancesSensorEntityDescription(
        key="swap_use",
        type="memswap",
        translation_key="swap_use",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("memswap", "swap_free"): GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        translation_key="swap_free",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("load", "processor_load"): GlancesSensorEntityDescription(
        key="processor_load",
        type="load",
        translation_key="processor_load",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_running"): GlancesSensorEntityDescription(
        key="process_running",
        type="processcount",
        translation_key="process_running",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_total"): GlancesSensorEntityDescription(
        key="process_total",
        type="processcount",
        translation_key="process_total",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_thread"): GlancesSensorEntityDescription(
        key="process_thread",
        type="processcount",
        translation_key="process_threads",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("processcount", "process_sleeping"): GlancesSensorEntityDescription(
        key="process_sleeping",
        type="processcount",
        translation_key="process_sleeping",
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("cpu", "cpu_use_percent"): GlancesSensorEntityDescription(
        key="cpu_use_percent",
        type="cpu",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon=CPU_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "temperature_core"): GlancesSensorEntityDescription(
        key="temperature_core",
        type="sensors",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "temperature_hdd"): GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "fan_speed"): GlancesSensorEntityDescription(
        key="fan_speed",
        type="sensors",
        translation_key="fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensors", "battery"): GlancesSensorEntityDescription(
        key="battery",
        type="sensors",
        translation_key="charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_active"): GlancesSensorEntityDescription(
        key="docker_active",
        type="docker",
        translation_key="container_active",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_cpu_use"): GlancesSensorEntityDescription(
        key="docker_cpu_use",
        type="docker",
        translation_key="container_cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("docker", "docker_memory_use"): GlancesSensorEntityDescription(
        key="docker_memory_use",
        type="docker",
        translation_key="container_memory_used",
        native_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("raid", "available"): GlancesSensorEntityDescription(
        key="available",
        type="raid",
        translation_key="raid_available",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("raid", "used"): GlancesSensorEntityDescription(
        key="used",
        type="raid",
        translation_key="raid_used",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("computed", "uptime"): GlancesSensorEntityDescription(
        key="uptime",
        type="computed",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ("gpu", "mem"): GlancesSensorEntityDescription(
        key="mem",
        type="gpu",
        translation_key="gpu_memory_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("gpu", "proc"): GlancesSensorEntityDescription(
        key="proc",
        type="gpu",
        translation_key="gpu_processor_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ("gpu", "temperature"): GlancesSensorEntityDescription(
        key="temperature",
        type="gpu",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("gpu", "fan_speed"): GlancesSensorEntityDescription(
        key="fan_speed",
        type="gpu",
        translation_key="fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("network", "rx"): GlancesSensorEntityDescription(
        key="rx",
        type="network",
        translation_key="network_rx",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("network", "tx"): GlancesSensorEntityDescription(
        key="tx",
        type="network",
        translation_key="network_tx",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _cleanup_orphan_entities(
    hass: HomeAssistant,
    config_entry: GlancesConfigEntry,
    coordinator: GlancesDataUpdateCoordinator,
) -> None:
    """Remove registry entries for dynamic devices no longer in the API data.

    Runs once at setup so entities registered before the dynamic-removal
    behavior was added (or while Home Assistant was offline) get cleaned up
    instead of lingering as STATE_UNAVAILABLE.
    """
    if not coordinator.data:
        return

    # Map description.key -> set of dynamic sensor_types that use it. Used to
    # locate which top-level data dict a registry entry belonged to, given
    # only its unique_id suffix.
    key_to_types: dict[str, set[str]] = {}
    for (sensor_type, _param), description in SENSOR_TYPES.items():
        if sensor_type in DYNAMIC_TYPES:
            key_to_types.setdefault(description.key, set()).add(sensor_type)

    entry_id = config_entry.entry_id
    prefix = f"{entry_id}-"
    ent_reg = er.async_get(hass)

    for entry in er.async_entries_for_config_entry(ent_reg, entry_id):
        if entry.domain != "sensor" or not entry.unique_id.startswith(prefix):
            continue
        rest = entry.unique_id.removeprefix(prefix)
        # Static singleton entities have an empty sensor_label, producing a
        # "--key" suffix; skip them so we don't remove them during a
        # transient API gap.
        if rest.startswith("-"):
            continue
        for desc_key, types in key_to_types.items():
            if not rest.endswith(f"-{desc_key}"):
                continue
            label = rest[: -(len(desc_key) + 1)]
            present_parents = [
                coordinator.data[t] for t in types if t in coordinator.data
            ]
            # Only remove when at least one candidate parent dict is present
            # and the label is missing from every present parent — mirrors the
            # guard in GlancesSensor._handle_coordinator_update.
            if present_parents and all(
                label not in parent for parent in present_parents
            ):
                ent_reg.async_remove(entry.entity_id)
            break


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GlancesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Glances sensors."""

    coordinator = config_entry.runtime_data
    _cleanup_orphan_entities(hass, config_entry, coordinator)
    created: set[tuple[str, str, str]] = set()

    @callback
    def _add_new_entities() -> None:
        new_entities: list[GlancesSensor] = []
        for sensor_type, sensors in coordinator.data.items():
            if sensor_type in DYNAMIC_TYPES:
                for sensor_label, params in sensors.items():
                    for param in params:
                        key = (sensor_type, sensor_label, param)
                        if key in created:
                            continue
                        if (
                            description := SENSOR_TYPES.get((sensor_type, param))
                        ) is None:
                            continue
                        created.add(key)
                        new_entities.append(
                            GlancesSensor(coordinator, description, sensor_label)
                        )
            else:
                for sensor in sensors:
                    key = (sensor_type, "", sensor)
                    if key in created:
                        continue
                    if (description := SENSOR_TYPES.get((sensor_type, sensor))) is None:
                        continue
                    created.add(key)
                    new_entities.append(GlancesSensor(coordinator, description))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class GlancesSensor(CoordinatorEntity[GlancesDataUpdateCoordinator], SensorEntity):
    """Implementation of a Glances sensor."""

    entity_description: GlancesSensorEntityDescription
    _attr_has_entity_name = True
    _data_valid: bool = False

    def __init__(
        self,
        coordinator: GlancesDataUpdateCoordinator,
        description: GlancesSensorEntityDescription,
        sensor_label: str = "",
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_label = sensor_label
        self.entity_description = description
        if sensor_label:
            self._attr_translation_placeholders = {"sensor_label": sensor_label}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Glances",
            name=coordinator.host,
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{sensor_label}-{description.key}"
        )
        self._update_native_value()

    @property
    def available(self) -> bool:
        """Set sensor unavailable when native value is invalid."""
        return super().available and self._data_valid

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.type in DYNAMIC_TYPES:
            parent = self.coordinator.data.get(self.entity_description.type)
            # Only auto-remove when the parent type is present but the label is
            # missing — a missing parent type is treated as a transient API
            # gap and leaves the entity unavailable instead.
            if parent is not None and self._sensor_label not in parent:
                er.async_get(self.hass).async_remove(self.entity_id)
                return
        self._update_native_value()
        super()._handle_coordinator_update()

    def _update_native_value(self) -> None:
        """Update sensor native value from coordinator data."""
        data = self.coordinator.data.get(self.entity_description.type)
        if data and (dict_val := data.get(self._sensor_label)):
            self._attr_native_value = dict_val.get(self.entity_description.key)
        elif data and (self.entity_description.key in data):
            self._attr_native_value = data.get(self.entity_description.key)
        else:
            self._attr_native_value = None
        self._update_data_valid()

    def _update_data_valid(self) -> None:
        self._data_valid = self._attr_native_value is not None and (
            not self._numeric_state_expected
            or isinstance(self._attr_native_value, (int, float))
            or (
                isinstance(self._attr_native_value, str)
                and self._attr_native_value.isnumeric()
            )
        )
