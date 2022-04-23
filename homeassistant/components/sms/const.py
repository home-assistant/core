"""Constants for sms Component."""

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "sms"
SMS_GATEWAY = "SMS_GATEWAY"
SMS_STATE_UNREAD = "UnRead"
SIGNAL_COORDINATOR = "signal_gateway"
NETWORK_COORDINATOR = "network_gateway"
GAMMU_DATA = "data"
GATEWAY = "gateway"

DEFAULT_SCAN_INTERVAL = 60

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
