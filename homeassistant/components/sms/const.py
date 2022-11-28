"""Constants for sms Component."""
from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "sms"
SMS_GATEWAY = "SMS_GATEWAY"
HASS_CONFIG = "sms_hass_config"
SMS_STATE_UNREAD = "UnRead"
SIGNAL_COORDINATOR = "signal_coordinator"
NETWORK_COORDINATOR = "network_coordinator"
GATEWAY = "gateway"
DEFAULT_SCAN_INTERVAL = 30
CONF_BAUD_SPEED = "baud_speed"
CONF_UNICODE = "unicode"
DEFAULT_BAUD_SPEED = "0"
DEFAULT_BAUD_SPEEDS = [
    {"value": DEFAULT_BAUD_SPEED, "label": "Auto"},
    {"value": "50", "label": "50"},
    {"value": "75", "label": "75"},
    {"value": "110", "label": "110"},
    {"value": "134", "label": "134"},
    {"value": "150", "label": "150"},
    {"value": "200", "label": "200"},
    {"value": "300", "label": "300"},
    {"value": "600", "label": "600"},
    {"value": "1200", "label": "1200"},
    {"value": "1800", "label": "1800"},
    {"value": "2400", "label": "2400"},
    {"value": "4800", "label": "4800"},
    {"value": "9600", "label": "9600"},
    {"value": "19200", "label": "19200"},
    {"value": "28800", "label": "28800"},
    {"value": "38400", "label": "38400"},
    {"value": "57600", "label": "57600"},
    {"value": "76800", "label": "76800"},
    {"value": "115200", "label": "115200"},
]

SIGNAL_SENSORS: Final[dict[str, SensorEntityDescription]] = {
    "SignalStrength": SensorEntityDescription(
        key="SignalStrength",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
    ),
    "SignalPercent": SensorEntityDescription(
        key="SignalPercent",
        icon="mdi:signal-cellular-3",
        name="Signal Percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=True,
    ),
    "BitErrorRate": SensorEntityDescription(
        key="BitErrorRate",
        name="Bit Error Rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
}

NETWORK_SENSORS: Final[dict[str, SensorEntityDescription]] = {
    "NetworkName": SensorEntityDescription(
        key="NetworkName",
        name="Network Name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "State": SensorEntityDescription(
        key="State",
        name="Network Status",
        entity_registry_enabled_default=True,
    ),
    "NetworkCode": SensorEntityDescription(
        key="NetworkCode",
        name="GSM network code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "CID": SensorEntityDescription(
        key="CID",
        name="Cell ID",
        icon="mdi:radio-tower",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "LAC": SensorEntityDescription(
        key="LAC",
        name="Local Area Code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}
