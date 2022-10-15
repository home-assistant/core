"""Support gathering system information of hosts which are running glances."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GlancesData
from .const import CPU_ICON, DATA_UPDATED, DOMAIN


@dataclass
class GlancesSensorEntityDescription(SensorEntityDescription):
    """Describe Glances sensor entity."""

    type: str | None = None
    name_suffix: str | None = None


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
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:harddisk",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="disk_free",
        type="fs",
        name_suffix="free",
        native_unit_of_measurement=DATA_GIBIBYTES,
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
        native_unit_of_measurement=DATA_MEBIBYTES,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="memory_free",
        type="mem",
        name_suffix="RAM free",
        native_unit_of_measurement=DATA_MEBIBYTES,
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
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="swap_free",
        type="memswap",
        name_suffix="Swap free",
        native_unit_of_measurement=DATA_GIBIBYTES,
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
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GlancesSensorEntityDescription(
        key="temperature_hdd",
        type="sensors",
        name_suffix="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
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
        native_unit_of_measurement=DATA_MEBIBYTES,
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

    client: GlancesData = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data.get(CONF_NAME)
    dev = []

    @callback
    def _migrate_old_unique_ids(
        hass: HomeAssistant, old_unique_id: str, new_key: str
    ) -> None:
        """Migrate unique IDs to the new format."""
        ent_reg = entity_registry.async_get(hass)

        if entity_id := ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, old_unique_id
        ):

            ent_reg.async_update_entity(
                entity_id, new_unique_id=f"{config_entry.entry_id}-{new_key}"
            )

    for description in SENSOR_TYPES:
        if description.type == "fs":
            # fs will provide a list of disks attached
            for disk in client.api.data[description.type]:
                _migrate_old_unique_ids(
                    hass,
                    f"{client.host}-{name} {disk['mnt_point']} {description.name_suffix}",
                    f"{disk['mnt_point']}-{description.key}",
                )
                dev.append(
                    GlancesSensor(
                        client,
                        name,
                        disk["mnt_point"],
                        description,
                    )
                )
        elif description.type == "sensors":
            # sensors will provide temp for different devices
            for sensor in client.api.data[description.type]:
                if sensor["type"] == description.key:
                    _migrate_old_unique_ids(
                        hass,
                        f"{client.host}-{name} {sensor['label']} {description.name_suffix}",
                        f"{sensor['label']}-{description.key}",
                    )
                    dev.append(
                        GlancesSensor(
                            client,
                            name,
                            sensor["label"],
                            description,
                        )
                    )
        elif description.type == "raid":
            for raid_device in client.api.data[description.type]:
                _migrate_old_unique_ids(
                    hass,
                    f"{client.host}-{name} {raid_device} {description.name_suffix}",
                    f"{raid_device}-{description.key}",
                )
                dev.append(GlancesSensor(client, name, raid_device, description))
        elif client.api.data[description.type]:
            _migrate_old_unique_ids(
                hass,
                f"{client.host}-{name}  {description.name_suffix}",
                f"-{description.key}",
            )
            dev.append(
                GlancesSensor(
                    client,
                    name,
                    "",
                    description,
                )
            )

    async_add_entities(dev, True)


class GlancesSensor(SensorEntity):
    """Implementation of a Glances sensor."""

    entity_description: GlancesSensorEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        glances_data: GlancesData,
        name: str | None,
        sensor_name_prefix: str,
        description: GlancesSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.glances_data = glances_data
        self._sensor_name_prefix = sensor_name_prefix
        self.unsub_update: CALLBACK_TYPE | None = None

        self.entity_description = description
        self._attr_name = f"{sensor_name_prefix} {description.name_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, glances_data.config_entry.entry_id)},
            manufacturer="Glances",
            name=name or glances_data.config_entry.data[CONF_HOST],
        )
        self._attr_unique_id = f"{self.glances_data.config_entry.entry_id}-{sensor_name_prefix}-{description.key}"

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self.glances_data.available

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self) -> None:
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self) -> None:
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
        self.unsub_update = None

    async def async_update(self) -> None:  # noqa: C901
        """Get the latest data from REST API."""
        if (value := self.glances_data.api.data) is None:
            return

        if self.entity_description.type == "fs":
            for var in value["fs"]:
                if var["mnt_point"] == self._sensor_name_prefix:
                    disk = var
                    break
            if self.entity_description.key == "disk_free":
                try:
                    self._attr_native_value = round(disk["free"] / 1024**3, 1)
                except KeyError:
                    self._attr_native_value = round(
                        (disk["size"] - disk["used"]) / 1024**3,
                        1,
                    )
            elif self.entity_description.key == "disk_use":
                self._attr_native_value = round(disk["used"] / 1024**3, 1)
            elif self.entity_description.key == "disk_use_percent":
                self._attr_native_value = disk["percent"]
        elif self.entity_description.key == "battery":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "battery"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._attr_native_value = sensor["value"]
        elif self.entity_description.key == "fan_speed":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "fan_speed"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._attr_native_value = sensor["value"]
        elif self.entity_description.key == "temperature_core":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "temperature_core"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._attr_native_value = sensor["value"]
        elif self.entity_description.key == "temperature_hdd":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "temperature_hdd"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._attr_native_value = sensor["value"]
        elif self.entity_description.key == "memory_use_percent":
            self._attr_native_value = value["mem"]["percent"]
        elif self.entity_description.key == "memory_use":
            self._attr_native_value = round(value["mem"]["used"] / 1024**2, 1)
        elif self.entity_description.key == "memory_free":
            self._attr_native_value = round(value["mem"]["free"] / 1024**2, 1)
        elif self.entity_description.key == "swap_use_percent":
            self._attr_native_value = value["memswap"]["percent"]
        elif self.entity_description.key == "swap_use":
            self._attr_native_value = round(value["memswap"]["used"] / 1024**3, 1)
        elif self.entity_description.key == "swap_free":
            self._attr_native_value = round(value["memswap"]["free"] / 1024**3, 1)
        elif self.entity_description.key == "processor_load":
            # Windows systems don't provide load details
            try:
                self._attr_native_value = value["load"]["min15"]
            except KeyError:
                self._attr_native_value = value["cpu"]["total"]
        elif self.entity_description.key == "process_running":
            self._attr_native_value = value["processcount"]["running"]
        elif self.entity_description.key == "process_total":
            self._attr_native_value = value["processcount"]["total"]
        elif self.entity_description.key == "process_thread":
            self._attr_native_value = value["processcount"]["thread"]
        elif self.entity_description.key == "process_sleeping":
            self._attr_native_value = value["processcount"]["sleeping"]
        elif self.entity_description.key == "cpu_use_percent":
            self._attr_native_value = value["quicklook"]["cpu"]
        elif self.entity_description.key == "docker_active":
            count = 0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        count += 1
                self._attr_native_value = count
            except KeyError:
                self._attr_native_value = count
        elif self.entity_description.key == "docker_cpu_use":
            cpu_use = 0.0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        cpu_use += container["cpu"]["total"]
                    self._attr_native_value = round(cpu_use, 1)
            except KeyError:
                self._attr_native_value = STATE_UNAVAILABLE
        elif self.entity_description.key == "docker_memory_use":
            mem_use = 0.0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        mem_use += container["memory"]["usage"]
                    self._attr_native_value = round(mem_use / 1024**2, 1)
            except KeyError:
                self._attr_native_value = STATE_UNAVAILABLE
        elif self.entity_description.type == "raid":
            for raid_device, raid in value["raid"].items():
                if raid_device == self._sensor_name_prefix:
                    self._attr_native_value = raid[self.entity_description.key]
