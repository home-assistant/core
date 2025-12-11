"""Class for creation of Homeassistant Entities related to all Powersensor Sensor measurements."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN, SENSOR_NAME_FORMAT
from .PowersensorEntity import PowersensorEntity
from .SensorMeasurements import SensorMeasurements

_LOGGER = logging.getLogger(__name__)


_config: dict[SensorMeasurements, dict] = {
    SensorMeasurements.Battery: {
        "name": "Battery Level",
        "device_class": SensorDeviceClass.BATTERY,
        "unit": PERCENTAGE,
        "precision": 0,
        "event": "battery_level",
        "message_key": "volts",
        "callback": lambda v: max(
            min(100.0 * (v - 3.3) / 0.85, 100), 0
        ),  # 0% = 3.3 V , 100% = 4.15 V
    },
    SensorMeasurements.WATTS: {
        "name": "Power",
        "device_class": SensorDeviceClass.POWER,
        "unit": UnitOfPower.WATT,
        "precision": 1,
        "event": "average_power",
        "message_key": "watts",
    },
    SensorMeasurements.SUMMATION_ENERGY: {
        "name": "Total Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "precision": 2,
        "state_class": SensorStateClass.TOTAL,
        "event": "summation_energy",
        "message_key": "summation_joules",
        "callback": lambda v: v / 3600000.0,
    },
    SensorMeasurements.ROLE: {
        "name": "Device Role",
        "category": EntityCategory.DIAGNOSTIC,
        "event": "role",
        "message_key": "role",
    },
    SensorMeasurements.RSSI: {
        "name": "Signal strength (Bluetooth)",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "unit": SIGNAL_STRENGTH_DECIBELS,
        "precision": 1,
        "category": EntityCategory.DIAGNOSTIC,
        "event": "radio_signal_quality",
        "message_key": "average_rssi",
    },
}


class PowersensorSensorEntity(PowersensorEntity):
    """Powersensor Plug Class--designed to handle all measurements of the plug--perhaps less expressive."""

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        role: str,
        measurement_type: SensorMeasurements,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, mac, role, _config, measurement_type)
        self._model = "PowersensorSensor"
        self.measurement_type = measurement_type
        config = _config[measurement_type]
        self._measurement_name = config["name"]
        self._device_name = self._default_device_name()
        self._attr_name = f"{self._device_name} {self._measurement_name}"

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo for PowersensorSensor. Includes mac, name and model."""
        return {
            "identifiers": {(DOMAIN, self._mac)},
            "manufacturer": "Powersensor",
            "model": self._model,
            "name": self._device_name,
        }

    def _ensure_matching_prefix(self):
        if not self._attr_name.startswith(self._device_name):
            self._attr_name = f"{self._device_name} {self._measurement_name}"

    def _rename_based_on_role(self) -> bool:
        expected_name = self._default_device_name()
        if self._device_name != expected_name:
            self._device_name = expected_name
            self._ensure_matching_prefix()
            return True
        return False

    def _default_device_name(self) -> str:
        role2name = {
            "house-net": "Powersensor Mains Sensor ⚡",
            "solar": "Powersensor Solar Sensor ☀️",
            "water": "Powersensor Water Sensor 💧",
        }
        return (
            role2name[self._role]
            if self._role in ["house-net", "water", "solar"]
            else SENSOR_NAME_FORMAT % self._mac
        )
