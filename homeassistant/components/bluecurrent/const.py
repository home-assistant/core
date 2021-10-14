"""Constants for the BlueCurrent integration."""
import logging

from homeassistant.components.sensor import SensorEntityDescription

DOMAIN = "bluecurrent"

LOGGER = logging.getLogger(__package__)

PLATFORMS = ["sensor"]
CHARGE_POINTS = "CHARGE_POINTS"
DATA = "data"
DELAY_1 = 1
DELAY_2 = 20

EVSE_ID = "evse_id"
GRID_STATUS = "GRID_STATUS"
MODEL_TYPE = "model_type"
OBJECT = "object"
TIMESTAMP_KEYS = ("start_datetime", "stop_datetime", "offline_since")
VALUE_TYPES = "CH_STATUS"

SENSORS = (
    SensorEntityDescription(
        key="actual_v1",
        native_unit_of_measurement="V",
        device_class="voltage",
        name="Voltage Phase 1",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="actual_v2",
        native_unit_of_measurement="V",
        device_class="voltage",
        name="Voltage Phase 2",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="actual_v3",
        native_unit_of_measurement="V",
        device_class="voltage",
        name="Voltage Phase 3",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="avg_voltage",
        native_unit_of_measurement="V",
        device_class="voltage",
        name="Average Voltage",
    ),
    SensorEntityDescription(
        key="actual_p1",
        native_unit_of_measurement="A",
        device_class="current",
        name="Current Phase 1",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="actual_p2",
        native_unit_of_measurement="A",
        device_class="current",
        name="Current Phase 2",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="actual_p3",
        native_unit_of_measurement="A",
        device_class="current",
        name="Current Phase 3",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="avg_current",
        native_unit_of_measurement="A",
        device_class="current",
        name="Average Current",
    ),
    SensorEntityDescription(
        key="total_kw",
        native_unit_of_measurement="kW",
        device_class="power",
        name="Total kW",
    ),
    SensorEntityDescription(
        key="actual_kwh",
        native_unit_of_measurement="kWh",
        device_class="energy",
        name="Energy Usage",
        state_class="total_increasing",
    ),
    SensorEntityDescription(
        key="start_datetime",
        native_unit_of_measurement="Timestamp",
        device_class="timestamp",
        name="Started On",
    ),
    SensorEntityDescription(
        key="stop_datetime",
        native_unit_of_measurement="Timestamp",
        device_class="timestamp",
        name="Stopped On",
    ),
    SensorEntityDescription(
        key="offline_since",
        native_unit_of_measurement="Timestamp",
        device_class="timestamp",
        name="Offline Since",
    ),
    SensorEntityDescription(
        key="total_cost",
        native_unit_of_measurement="EUR",
        device_class="monetary",
        name="Total Cost",
    ),
    SensorEntityDescription(
        key="vehicle_status",
        name="Vehicle Status",
        icon="mdi:car",
        device_class="bluecurrent__vehicle_status",
    ),
    SensorEntityDescription(
        key="activity",
        name="Activity",
        icon="mdi:ev-station",
        device_class="bluecurrent__activity",
    ),
    SensorEntityDescription(
        key="max_usage",
        name="Max Usage",
        icon="mdi:gauge-full",
        native_unit_of_measurement="A",
    ),
    SensorEntityDescription(
        key="smartcharging_max_usage",
        name="Smart Charging Max Usage",
        icon="mdi:gauge-full",
        native_unit_of_measurement="A",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="max_offline",
        name="Offline Max Usage",
        icon="mdi:gauge-full",
        native_unit_of_measurement="A",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="current_left",
        name="Remaining current",
        icon="mdi:gauge",
        native_unit_of_measurement="A",
        entity_registry_enabled_default=False,
    ),
)

GRID_SENSORS = (
    SensorEntityDescription(
        key="grid_actual_p1",
        native_unit_of_measurement="A",
        device_class="current",
        name="Grid Current Phase 1",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="grid_actual_p2",
        native_unit_of_measurement="A",
        device_class="current",
        name="Grid Current Phase 2",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="grid_actual_p3",
        native_unit_of_measurement="A",
        device_class="current",
        name="Grid Current Phase 3",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="grid_avg_current",
        native_unit_of_measurement="A",
        device_class="current",
        name="Average Grid Current",
    ),
    SensorEntityDescription(
        key="grid_max_current",
        native_unit_of_measurement="A",
        device_class="current",
        name="Max Grid Current",
    ),
)
