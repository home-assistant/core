"""Support for Lektrico charging station sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_FRIENDLY_NAME,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDevice
from .const import DOMAIN


@dataclass
class LektricoSensorEntityDescription(SensorEntityDescription):
    """A class that describes the Lektrico sensor entities."""

    value_fn: Any | None = None


SENSORS: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="charger_state",
        name="Charger State",
        value_fn=lambda x: x.charger_state,
    ),
    LektricoSensorEntityDescription(
        key="charging_time",
        name="Charging Time",
        native_unit_of_measurement=TIME_SECONDS,
        value_fn=lambda x: x.charging_time,
    ),
    LektricoSensorEntityDescription(
        key="current",
        name="Current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda x: x.current,
    ),
    LektricoSensorEntityDescription(
        key="instant_power",
        name="Instant Power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        value_fn=lambda x: x.instant_power,
    ),
    LektricoSensorEntityDescription(
        key="session_energy",
        name="Session Energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_fn=lambda x: x.session_energy,
    ),
    LektricoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda x: x.temperature,
    ),
    LektricoSensorEntityDescription(
        key="total_charged_energy",
        name="Total Charged Energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_fn=lambda x: x.total_charged_energy,
    ),
    LektricoSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        value_fn=lambda x: x.voltage,
    ),
    LektricoSensorEntityDescription(
        key="install_current",
        name="Install Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda x: x.install_current,
    ),
    LektricoSensorEntityDescription(
        key="dynamic_current",
        name="Dynamic Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda x: x.dynamic_current,
    ),
    LektricoSensorEntityDescription(
        key="led_max_brightness",
        name="Led Brightness",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda x: x.led_max_brightness,
    ),
    LektricoSensorEntityDescription(
        key="headless",
        name="No Authentication",
        value_fn=lambda x: x.headless,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    _lektrico_device: LektricoDevice = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        LektricoSensor(
            sensor_desc,
            _lektrico_device.serial_number,
            _lektrico_device.board_revision,
            _lektrico_device,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for sensor_desc in SENSORS
    ]

    async_add_entities(sensors, True)


class LektricoSensor(CoordinatorEntity, SensorEntity):
    """The entity class for Lektrico charging stations sensors."""

    entity_description: LektricoSensorEntityDescription

    def __init__(
        self,
        description: LektricoSensorEntityDescription,
        serial_number: str,
        board_revision: str,
        _lektrico_device: LektricoDevice,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(_lektrico_device.coordinator)
        self.friendly_name = friendly_name
        self.serial_number = serial_number
        self.board_revision = board_revision
        self.entity_description = description

        self._attr_name = f"{self.friendly_name} {description.name}"
        self._attr_unique_id = f"{serial_number}_{description.name}"
        # ex: 500006_Led Brightness

        self._lektrico_device = _lektrico_device

    @property
    def native_value(self) -> float | str | Any | None:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(
                self._lektrico_device.coordinator.data
            )
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.native_unit_of_measurement is not None:
            return self.entity_description.native_unit_of_measurement
        return super().native_unit_of_measurement

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Lektrico charger."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.serial_number)},
            ATTR_NAME: self.friendly_name,
            ATTR_MANUFACTURER: "Lektrico",
            ATTR_MODEL: f"1P7K {self.serial_number} rev.{self.board_revision}",
            ATTR_SW_VERSION: self._lektrico_device.coordinator.data.fw_version,
        }
