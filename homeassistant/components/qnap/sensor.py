"""Support for QNAP NAS Sensors."""
import logging

from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_NAME,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfInformation,
    UnitOfDataRate,
)

from .const import (
    ATTR_DRIVE,
    ATTR_IP,
    ATTR_MAC,
    ATTR_MASK,
    ATTR_MAX_SPEED,
    ATTR_MEMORY_SIZE,
    ATTR_MODEL,
    ATTR_PACKETS_ERR,
    ATTR_PACKETS_RX,
    ATTR_PACKETS_TX,
    ATTR_SERIAL,
    ATTR_TYPE,
    ATTR_UPTIME,
    ATTR_VOLUME_SIZE,
    DEFAULT_NAME,
    DOMAIN,
    VOLUME_NAME,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    uid = config_entry.unique_id
    sensors: list[QNAPSensor] = []

    sensors.extend(
        [QNAPSystemSensor(coordinator, description, uid) for description in BAS_SENSOR]
    )

    sensors.extend(
        [QNAPCPUSensor(coordinator, description, uid) for description in CPU_SENSOR]
    )

    sensors.extend(
        [QNAPMemorySensor(coordinator, description, uid) for description in MEM_SENSOR]
    )

    # Network sensors
    sensors.extend(
        [
            QNAPNetworkSensor(coordinator, description, uid, nic)
            for nic in coordinator.data["system_stats"]["nics"].keys()
            for description in NET_SENSOR
        ]
    )

    # Drive sensors
    sensors.extend(
        [
            QNAPDriveSensor(coordinator, description, uid, drive)
            for drive in coordinator.data["smart_drive_health"].keys()
            for description in DRI_SENSOR
        ]
    )

    # Volume sensors
    sensors.extend(
        [
            QNAPVolumeSensor(coordinator, description, uid, volume)
            for volume in coordinator.data["volumes"].keys()
            for description in VOL_SENSOR
        ]
    )

    # Folders sensors
    sensors.extend(
        [
            QNAPFolderSensor(coordinator, description, uid, volume, folder["sharename"])
            for volume in coordinator.data["volumes"].keys()
            for folder in coordinator.data["volumes"][volume].get("folders", [])
            for description in FOL_SENSOR
        ]
    )
    async_add_entities(sensors)


def round_nicely(number):
    """Round a number based on its size (so it looks nice)."""
    if number < 10:
        return round(number, 2)
    if number < 100:
        return round(number, 1)

    return round(number)


@dataclass
class QNapSensorEntityDescription(SensorEntityDescription):
    """Represents an Flow Sensor."""

    stype: str | None = None


SENSOR_TYPES: tuple[QNapSensorEntityDescription, ...] = (
    QNapSensorEntityDescription(
        stype="basic",
        key="status",
        name="Health",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    QNapSensorEntityDescription(
        stype="basic",
        key="system_temp",
        name="System Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="cpu",
        key="cpu_temp",
        name="CPU Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="cpu",
        key="cpu_usage",
        name="CPU Usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="memory",
        key="memory_free",
        name="Memory Available",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="memory",
        key="memory_used",
        name="Memory Used",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="memory",
        key="memory_percent_used",
        name="Memory Usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="network",
        key="network_link_status",
        name="Network Link",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    QNapSensorEntityDescription(
        stype="network",
        key="network_tx",
        name="Network Up",
        native_unit_of_measurement=UnitOfDataRate.MEBIBYTES_PER_SECOND,
        icon="mdi:upload",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="network",
        key="network_rx",
        name="Network Down",
        native_unit_of_measurement=UnitOfDataRate.MEBIBYTES_PER_SECOND,
        icon="mdi:download",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="drive",
        key="drive_smart_status",
        name="SMART Status",
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=False,
    ),
    QNapSensorEntityDescription(
        stype="drive",
        key="drive_temp",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="folder",
        key="folder_size_used",
        name="Used Space",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="folder",
        key="folder_percentage_used",
        name="Folder Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="volume",
        key="volume_size_used",
        name="Used Space",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="volume",
        key="volume_size_free",
        name="Free Space",
        native_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="volume",
        key="volume_percentage_used",
        name="Volume Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-pie",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
BAS_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "basic"]
CPU_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "cpu"]
MEM_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "memory"]
NET_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "network"]
DRI_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "drive"]
FOL_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "folder"]
VOL_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "volume"]
    
class QNAPSensor(CoordinatorEntity, SensorEntity):
    """Base class for a QNAP sensor."""

    def __init__(
        self, coordinator, description, uid, monitor_device=None, monitor_subdevice=None
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entity_description = description
        self.uid = uid
        self.device_name = self.coordinator.data["system_stats"]["system"]["name"]
        self.monitor_device = monitor_device
        self.monitor_subdevice = monitor_subdevice

    @property
    def unique_id(self):
        """Return unique_id."""
        return f"{self.uid}_{self.name}"

    @property
    def coordinator_context(self):
        return None
    
    @property
    def name(self):
        """Return the name of the sensor, if any."""
        if self.monitor_device is not None:
            return f"{self.device_name} {self.monitor_device} - {self.entity_description.name}"
        return f"{self.device_name} {self.entity_description.name}"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.uid)},
            "name": self.device_name,
            "model": self.coordinator.data["system_stats"]["system"]["model"],
            "sw_version": self.coordinator.data["system_stats"]["firmware"]["version"],
            "manufacturer": DEFAULT_NAME,
        }


class QNAPCPUSensor(QNAPSensor):
    """A QNAP sensor that monitors CPU stats."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == "cpu_temp":
            return self.coordinator.data["system_stats"]["cpu"]["temp_c"]
        if self.entity_description.key == "cpu_usage":
            return self.coordinator.data["system_stats"]["cpu"]["usage_percent"]


class QNAPMemorySensor(QNAPSensor):
    """A QNAP sensor that monitors memory stats."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        free = float(self.coordinator.data["system_stats"]["memory"]["free"]) / 1024
        if self.entity_description.key == "memory_free":
            return round_nicely(free)

        total = float(self.coordinator.data["system_stats"]["memory"]["total"]) / 1024

        used = total - free
        if self.entity_description.key == "memory_used":
            return round_nicely(used)

        if self.entity_description.key == "memory_percent_used":
            return round(used / total * 100)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["system_stats"]["memory"]
            size = round_nicely(float(data["total"]) / 1024)
            return {ATTR_MEMORY_SIZE: f"{size} {UnitOfInformation.GIBIBYTES}"}


class QNAPSystemSensor(QNAPSensor):
    """A QNAP sensor that monitors overall system health."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == "status":
            return self.coordinator.data["system_health"]

        if self.entity_description.key == "system_temp":
            return int(self.coordinator.data["system_stats"]["system"]["temp_c"])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["system_stats"]
            days = int(data["uptime"]["days"])
            hours = int(data["uptime"]["hours"])
            minutes = int(data["uptime"]["minutes"])

            return {
                ATTR_NAME: data["system"]["name"],
                ATTR_MODEL: data["system"]["model"],
                ATTR_SERIAL: data["system"]["serial_number"],
                ATTR_UPTIME: f"{days:0>2d}d {hours:0>2d}h {minutes:0>2d}m",
            }


class QNAPNetworkSensor(QNAPSensor):
    """A QNAP sensor that monitors network stats."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == "network_link_status":
            nic = self.coordinator.data["system_stats"]["nics"][self.monitor_device]
            return nic["link_status"]

        data = self.coordinator.data["bandwidth"][self.monitor_device]
        if self.entity_description.key == "network_tx":
            return round_nicely(data["tx"] / 1024 / 1024)

        if self.entity_description.key == "network_rx":
            return round_nicely(data["rx"] / 1024 / 1024)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["system_stats"]["nics"][self.monitor_device]
            return {
                ATTR_IP: data["ip"],
                ATTR_MASK: data["mask"],
                ATTR_MAC: data["mac"],
                ATTR_MAX_SPEED: data["max_speed"],
                ATTR_PACKETS_TX: data["tx_packets"],
                ATTR_PACKETS_RX: data["rx_packets"],
                ATTR_PACKETS_ERR: data["err_packets"],
            }


class QNAPDriveSensor(QNAPSensor):
    """A QNAP sensor that monitors HDD/SSD drive stats."""

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return f"{self.device_name} Drive {self.monitor_device} - {self.entity_description.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data["smart_drive_health"][self.monitor_device]

        if self.entity_description.key == "drive_smart_status":
            return data["health"]

        if self.entity_description.key == "drive_temp":
            return int(data["temp_c"]) if data["temp_c"] is not None else 0

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["smart_drive_health"][self.monitor_device]
            return {
                ATTR_DRIVE: data["drive_number"],
                ATTR_MODEL: data["model"],
                ATTR_SERIAL: data["serial"],
                ATTR_TYPE: data["type"],
            }


class QNAPVolumeSensor(QNAPSensor):
    """A QNAP sensor that monitors storage volume stats."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data["volumes"][self.monitor_device]

        free_gb = int(data["free_size"]) / 1024 / 1024 / 1024
        if self.entity_description.key == "volume_size_free":
            return round_nicely(free_gb)

        total_gb = int(data["total_size"]) / 1024 / 1024 / 1024

        used_gb = total_gb - free_gb
        if self.entity_description.key == "volume_size_used":
            return round_nicely(used_gb)

        if self.entity_description.key == "volume_percentage_used":
            return round(used_gb / total_gb * 100)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["volumes"][self.monitor_device]
            total_gb = int(data["total_size"]) / 1024 / 1024 / 1024

            return {ATTR_VOLUME_SIZE: f"{round_nicely(total_gb)} {UnitOfInformation.GIBIBYTES}"}


class QNAPFolderSensor(QNAPSensor):
    """A QNAP sensor that monitors storage folder stats."""

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return f"{self.device_name} Folder {self.monitor_subdevice} - {self.entity_description.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        for folder in self.coordinator.data["volumes"][self.monitor_device]["folders"]:
            if folder["sharename"] == self.monitor_subdevice:
                vol = self.coordinator.data["volumes"][self.monitor_device]
                used_gb = int(folder["used_size"]) / 1024 / 1024 / 1024
                total_gb = int(vol["total_size"]) / 1024 / 1024 / 1024

        if self.entity_description.key == "folder_size_used":
            return round_nicely(used_gb)

        if self.entity_description.key == "folder_percentage_used":
            return round(used_gb / total_gb * 100)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            data = self.coordinator.data["volumes"][self.monitor_device]
            total_gb = int(data["total_size"]) / 1024 / 1024 / 1024
            volume_name = self.monitor_device

            return {
                ATTR_VOLUME_SIZE: f"{round_nicely(total_gb)} {UnitOfInformation.GIBIBYTES}",
                VOLUME_NAME: volume_name,
            }
