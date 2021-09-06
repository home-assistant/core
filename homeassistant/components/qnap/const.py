"""The Qnap constants."""
from dataclasses import dataclass
from typing import Tuple
from homeassistant.components.sensor import (
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    TEMP_CELSIUS,
    SensorEntityDescription,
)
from homeassistant.const import (
    DATA_GIBIBYTES,
    DATA_RATE_MEBIBYTES_PER_SECOND,
    PERCENTAGE,
)

ATTR_DRIVE = "Drive"
ATTR_ENABLED = "Sensor Enabled"
ATTR_IP = "IP Address"
ATTR_MAC = "MAC Address"
ATTR_MASK = "Mask"
ATTR_MAX_SPEED = "Max Speed"
ATTR_MEMORY_SIZE = "Memory Size"
ATTR_MODEL = "Model"
ATTR_PACKETS_TX = "Packets (TX)"
ATTR_PACKETS_RX = "Packets (RX)"
ATTR_PACKETS_ERR = "Packets (Err)"
ATTR_SERIAL = "Serial #"
ATTR_TYPE = "Type"
ATTR_UPTIME = "Uptime"
ATTR_VOLUME_SIZE = "Volume Size"

PLATFORMS = ["sensor"]
DEFAULT_NAME = "QNAP"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 5
DOMAIN = "qnap"

NOTIFICATION_ID = "qnap_notification"
NOTIFICATION_TITLE = "QNAP Sensor Setup"


@dataclass
class QNapSensorEntityDescription(SensorEntityDescription):
    """Represents an Flow Sensor."""

    stype: str | None = None


SENSOR_TYPES: Tuple[QNapSensorEntityDescription, ...] = (
    QNapSensorEntityDescription(
        stype="basic",
        key="status",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=True,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="basic",
        key="system_temp",
        name="System Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        icon="mdi:thermometer",
        entity_registry_enabled_default=True,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="cpu",
        key="cpu_temp",
        name="CPU Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="cpu",
        key="cpu_usage",
        name="CPU Usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        entity_registry_enabled_default=True,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="memory",
        key="memory_free",
        name="Memory Available",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="memory",
        key="memory_used",
        name="Memory Used",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="memory",
        key="memory_percent_used",
        name="Memory Usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        entity_registry_enabled_default=True,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="network",
        key="network_link_status",
        name="Network Link",
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=True,
    ),
    QNapSensorEntityDescription(
        stype="network",
        key="network_tx",
        name="Network Up",
        native_unit_of_measurement=DATA_RATE_MEBIBYTES_PER_SECOND,
        icon="mdi:upload",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="network",
        key="network_rx",
        name="Network Down",
        native_unit_of_measurement=DATA_RATE_MEBIBYTES_PER_SECOND,
        icon="mdi:download",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
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
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="folder",
        key="folder_size_used",
        name="Used Space",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="folder",
        key="folder_percentage_used",
        name="Folder Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="volume",
        key="volume_size_used",
        name="Used Space",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="volume",
        key="volume_size_free",
        name="Free Space",
        native_unit_of_measurement=DATA_GIBIBYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    QNapSensorEntityDescription(
        stype="volume",
        key="volume_percentage_used",
        name="Volume Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=True,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

BAS_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "basic"]
CPU_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "cpu"]
MEM_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "memory"]
NET_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "network"]
DRI_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "drive"]
FOL_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "folder"]
VOL_SENSOR = [desc for desc in SENSOR_TYPES if desc.stype == "volume"]
