"""Constants for the Wallbox integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
)

DOMAIN = "wallbox"

CONF_STATION = "station"
CONF_ADDED_ENERGY_KEY = "added_energy"
CONF_ADDED_RANGE_KEY = "added_range"
CONF_CHARGING_POWER_KEY = "charging_power"
CONF_CHARGING_SPEED_KEY = "charging_speed"
CONF_CHARGING_TIME_KEY = "charging_time"
CONF_COST_KEY = "cost"
CONF_CURRENT_MODE_KEY = "current_mode"
CONF_DATA_KEY = "config_data"
CONF_DEPOT_PRICE_KEY = "depot_price"
CONF_MAX_AVAILABLE_POWER_KEY = "max_available_power"
CONF_MAX_CHARGING_CURRENT_KEY = "max_charging_current"
CONF_STATE_OF_CHARGE_KEY = "state_of_charge"
CONF_STATUS_DESCRIPTION_KEY = "status_description"

CONF_CONNECTIONS = "connections"


@dataclass
class WallboxSensorEntityDescription(SensorEntityDescription):
    """Describes Wallbox sensor entity."""

    precision: int | None = None


SENSOR_TYPES: dict[str, WallboxSensorEntityDescription] = {
    CONF_CHARGING_POWER_KEY: WallboxSensorEntityDescription(
        key=CONF_CHARGING_POWER_KEY,
        icon=None,
        name="Charging Power",
        precision=2,
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
    ),
    CONF_MAX_AVAILABLE_POWER_KEY: WallboxSensorEntityDescription(
        key=CONF_MAX_AVAILABLE_POWER_KEY,
        icon=None,
        name="Max Available Power",
        precision=0,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
    ),
    CONF_CHARGING_SPEED_KEY: WallboxSensorEntityDescription(
        key=CONF_CHARGING_SPEED_KEY,
        icon="mdi:speedometer",
        name="Charging Speed",
        precision=0,
        native_unit_of_measurement=None,
        device_class=None,
    ),
    CONF_ADDED_RANGE_KEY: WallboxSensorEntityDescription(
        key=CONF_ADDED_RANGE_KEY,
        icon="mdi:map-marker-distance",
        name="Added Range",
        precision=0,
        native_unit_of_measurement=LENGTH_KILOMETERS,
        device_class=None,
    ),
    CONF_ADDED_ENERGY_KEY: WallboxSensorEntityDescription(
        key=CONF_ADDED_ENERGY_KEY,
        icon=None,
        name="Added Energy",
        precision=2,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    CONF_CHARGING_TIME_KEY: WallboxSensorEntityDescription(
        key=CONF_CHARGING_TIME_KEY,
        icon="mdi:timer",
        name="Charging Time",
        precision=None,
        native_unit_of_measurement=None,
        device_class=None,
    ),
    CONF_COST_KEY: WallboxSensorEntityDescription(
        key=CONF_COST_KEY,
        icon="mdi:ev-station",
        name="Cost",
        precision=None,
        native_unit_of_measurement=None,
        device_class=None,
    ),
    CONF_STATE_OF_CHARGE_KEY: WallboxSensorEntityDescription(
        key=CONF_STATE_OF_CHARGE_KEY,
        icon=None,
        name="State of Charge",
        precision=None,
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    CONF_CURRENT_MODE_KEY: WallboxSensorEntityDescription(
        key=CONF_CURRENT_MODE_KEY,
        icon="mdi:ev-station",
        name="Current Mode",
        precision=None,
        native_unit_of_measurement=None,
        device_class=None,
    ),
    CONF_DEPOT_PRICE_KEY: WallboxSensorEntityDescription(
        key=CONF_DEPOT_PRICE_KEY,
        icon="mdi:ev-station",
        name="Depot Price",
        precision=2,
        native_unit_of_measurement=None,
        device_class=None,
    ),
    CONF_STATUS_DESCRIPTION_KEY: WallboxSensorEntityDescription(
        key=CONF_STATUS_DESCRIPTION_KEY,
        icon="mdi:ev-station",
        name="Status Description",
        precision=None,
        native_unit_of_measurement=None,
        device_class=None,
    ),
    CONF_MAX_CHARGING_CURRENT_KEY: WallboxSensorEntityDescription(
        key=CONF_MAX_CHARGING_CURRENT_KEY,
        icon=None,
        name="Max. Charging Current",
        precision=None,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
    ),
}
