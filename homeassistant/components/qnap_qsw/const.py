"""Constants for QNAP QSW integration."""
from __future__ import annotations

from typing import Final

from qnap_qsw.const import (
    DATA_CONDITION_ANOMALY,
    DATA_CONDITION_MESSAGE,
    DATA_FAN1_SPEED,
    DATA_FAN2_SPEED,
    DATA_MAC_ADDR,
    DATA_TEMP,
    DATA_TEMP_MAX,
    DATA_UPDATE,
    DATA_UPDATE_VERSION,
    DATA_UPTIME,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_UPDATE,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ENTITY_CATEGORY_DIAGNOSTIC,
    TEMP_CELSIUS,
)

DOMAIN: Final = "qnap_qsw"
MANUFACTURER: Final = "QNAP"
ASYNC_TIMEOUT: Final = 30

UNIT_RPM: Final = "rpm"

BINARY_SENSOR_TYPES: Final[tuple[BinarySensorEntityDescription, ...]] = (
    BinarySensorEntityDescription(
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_CONDITION_ANOMALY,
        name="Condition anomaly",
    ),
    BinarySensorEntityDescription(
        device_class=DEVICE_CLASS_UPDATE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_UPDATE,
        name="Firmware update",
    ),
)

SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_CONDITION_MESSAGE,
        name="Condition message",
    ),
    SensorEntityDescription(
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_FAN1_SPEED,
        name="Fan 1 Speed",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=UNIT_RPM,
    ),
    SensorEntityDescription(
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_FAN2_SPEED,
        name="Fan 2 Speed",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=UNIT_RPM,
    ),
    SensorEntityDescription(
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_MAC_ADDR,
        name="Mac address",
    ),
    SensorEntityDescription(
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_TEMP,
        name="Temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_TEMP_MAX,
        name="Maximum temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=DATA_UPDATE_VERSION,
        name="Firmware update version",
    ),
    SensorEntityDescription(
        device_class=DEVICE_CLASS_TIMESTAMP,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=DATA_UPTIME,
        name="Uptime",
    ),
)
