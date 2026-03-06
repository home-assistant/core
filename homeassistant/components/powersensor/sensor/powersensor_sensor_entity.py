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

from ..const import DOMAIN, ROLE_HOUSENET, ROLE_SOLAR, ROLE_WATER, SENSOR_NAME_FORMAT
from .powersensor_entity import PowersensorEntity, PowersensorSensorEntityDescription
from .sensor_measurements import SensorMeasurements

_LOGGER = logging.getLogger(__name__)


_config: dict[SensorMeasurements, PowersensorSensorEntityDescription] = {
    SensorMeasurements.BATTERY: PowersensorSensorEntityDescription(
        key="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        event="battery_level",
        message_key="volts",
        conversion_function=lambda v: max(
            min(100.0 * (v - 3.3) / 0.85, 100), 0
        ),  # 0% = 3.3 V , 100% = 4.15 V
    ),
    SensorMeasurements.WATTS: PowersensorSensorEntityDescription(
        key="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        event="average_power",
        message_key="watts",
    ),
    SensorMeasurements.SUMMATION_ENERGY: PowersensorSensorEntityDescription(
        key="Total Energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL,
        event="summation_energy",
        message_key="summation_joules",
        conversion_function=lambda v: v / 3600000.0,
    ),
    SensorMeasurements.ROLE: PowersensorSensorEntityDescription(
        key="Device Role",
        entity_category=EntityCategory.DIAGNOSTIC,
        event="role",
        message_key="role",
    ),
    SensorMeasurements.RSSI: PowersensorSensorEntityDescription(
        key="Signal strength (Bluetooth)",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        event="radio_signal_quality",
        message_key="average_rssi",
    ),
}


class PowersensorSensorEntity(PowersensorEntity):
    """Powersensor Sensor Class--designed to handle all measurements of the sensor."""

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
        config: PowersensorSensorEntityDescription = _config[measurement_type]
        self._measurement_name = config.key
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
            ROLE_HOUSENET: "Powersensor Mains Sensor ⚡",
            ROLE_SOLAR: "Powersensor Solar Sensor ☀️",
            ROLE_WATER: "Powersensor Water Sensor 💧",
        }
        return (
            role2name[self._role]
            if self._role in [ROLE_HOUSENET, ROLE_WATER, ROLE_SOLAR]
            else SENSOR_NAME_FORMAT % self._mac
        )
