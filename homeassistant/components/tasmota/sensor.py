"""Support for Tasmota sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hatasmota import const as hc, sensor as tasmota_sensor, status_sensor
from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.models import DiscoveryHashType

from homeassistant.components import sensor
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate

DEVICE_CLASS = "device_class"
STATE_CLASS = "state_class"
ICON = "icon"

# A Tasmota sensor type may be mapped to either a device class or an icon,
# both can only be set if the default device class icon is not appropriate
SENSOR_DEVICE_CLASS_ICON_MAP: dict[str, dict[str, Any]] = {
    hc.SENSOR_AMBIENT: {
        DEVICE_CLASS: SensorDeviceClass.ILLUMINANCE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_BATTERY: {
        DEVICE_CLASS: SensorDeviceClass.BATTERY,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_CCT: {
        ICON: "mdi:temperature-kelvin",
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_CO2: {
        DEVICE_CLASS: SensorDeviceClass.CO2,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_COLOR_BLUE: {ICON: "mdi:palette"},
    hc.SENSOR_COLOR_GREEN: {ICON: "mdi:palette"},
    hc.SENSOR_COLOR_RED: {ICON: "mdi:palette"},
    hc.SENSOR_CURRENT: {
        DEVICE_CLASS: SensorDeviceClass.CURRENT,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_CURRENT_NEUTRAL: {
        DEVICE_CLASS: SensorDeviceClass.CURRENT,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_DEWPOINT: {
        DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ICON: "mdi:weather-rainy",
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_DISTANCE: {
        DEVICE_CLASS: SensorDeviceClass.DISTANCE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_ECO2: {ICON: "mdi:molecule-co2"},
    hc.SENSOR_ENERGY: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL,
    },
    hc.SENSOR_ENERGY_EXPORT_ACTIVE: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL,
    },
    hc.SENSOR_ENERGY_EXPORT_REACTIVE: {STATE_CLASS: SensorStateClass.TOTAL},
    hc.SENSOR_ENERGY_EXPORT_TARIFF: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL,
    },
    hc.SENSOR_ENERGY_IMPORT_ACTIVE: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL,
    },
    hc.SENSOR_ENERGY_IMPORT_REACTIVE: {STATE_CLASS: SensorStateClass.TOTAL},
    hc.SENSOR_ENERGY_IMPORT_TODAY: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    },
    hc.SENSOR_ENERGY_IMPORT_TOTAL: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL,
    },
    hc.SENSOR_ENERGY_IMPORT_TOTAL_TARIFF: {
        DEVICE_CLASS: SensorDeviceClass.ENERGY,
        STATE_CLASS: SensorStateClass.TOTAL,
    },
    hc.SENSOR_ENERGY_IMPORT_YESTERDAY: {DEVICE_CLASS: SensorDeviceClass.ENERGY},
    hc.SENSOR_ENERGY_TOTAL_START_TIME: {ICON: "mdi:progress-clock"},
    hc.SENSOR_FREQUENCY: {
        DEVICE_CLASS: SensorDeviceClass.FREQUENCY,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_HUMIDITY: {
        DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_ILLUMINANCE: {
        DEVICE_CLASS: SensorDeviceClass.ILLUMINANCE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_POWER_ACTIVE: {
        DEVICE_CLASS: SensorDeviceClass.POWER,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_POWER_APPARENT: {
        DEVICE_CLASS: SensorDeviceClass.APPARENT_POWER,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_STATUS_IP: {ICON: "mdi:ip-network"},
    hc.SENSOR_STATUS_LINK_COUNT: {ICON: "mdi:counter"},
    hc.SENSOR_MOISTURE: {DEVICE_CLASS: SensorDeviceClass.MOISTURE},
    hc.SENSOR_STATUS_MQTT_COUNT: {ICON: "mdi:counter"},
    hc.SENSOR_PB0_3: {ICON: "mdi:flask"},
    hc.SENSOR_PB0_5: {ICON: "mdi:flask"},
    hc.SENSOR_PB10: {ICON: "mdi:flask"},
    hc.SENSOR_PB1: {ICON: "mdi:flask"},
    hc.SENSOR_PB2_5: {ICON: "mdi:flask"},
    hc.SENSOR_PB5: {ICON: "mdi:flask"},
    hc.SENSOR_PM10: {
        DEVICE_CLASS: SensorDeviceClass.PM10,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_PM1: {
        DEVICE_CLASS: SensorDeviceClass.PM1,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_PM2_5: {
        DEVICE_CLASS: SensorDeviceClass.PM25,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_POWER_FACTOR: {
        DEVICE_CLASS: SensorDeviceClass.POWER_FACTOR,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_POWER: {
        DEVICE_CLASS: SensorDeviceClass.POWER,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_PRESSURE: {
        DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_PRESSURE_AT_SEA_LEVEL: {
        DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_PROXIMITY: {ICON: "mdi:ruler"},
    hc.SENSOR_POWER_REACTIVE: {
        DEVICE_CLASS: SensorDeviceClass.REACTIVE_POWER,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_STATUS_LAST_RESTART_TIME: {DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    hc.SENSOR_STATUS_RESTART_REASON: {ICON: "mdi:information-outline"},
    hc.SENSOR_STATUS_SIGNAL: {
        DEVICE_CLASS: SensorDeviceClass.SIGNAL_STRENGTH,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_STATUS_RSSI: {
        ICON: "mdi:access-point",
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_STATUS_SSID: {ICON: "mdi:access-point-network"},
    hc.SENSOR_TEMPERATURE: {
        DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_TVOC: {ICON: "mdi:air-filter"},
    hc.SENSOR_VOLTAGE: {
        DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    hc.SENSOR_WEIGHT: {
        DEVICE_CLASS: SensorDeviceClass.WEIGHT,
        STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
}

SENSOR_UNIT_MAP = {
    hc.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: (
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    ),
    hc.CONCENTRATION_PARTS_PER_BILLION: CONCENTRATION_PARTS_PER_BILLION,
    hc.CONCENTRATION_PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    hc.ELECTRICAL_CURRENT_AMPERE: UnitOfElectricCurrent.AMPERE,
    hc.ELECTRICAL_VOLT_AMPERE: UnitOfApparentPower.VOLT_AMPERE,
    hc.ENERGY_KILO_WATT_HOUR: UnitOfEnergy.KILO_WATT_HOUR,
    hc.FREQUENCY_HERTZ: UnitOfFrequency.HERTZ,
    hc.LENGTH_CENTIMETERS: UnitOfLength.CENTIMETERS,
    hc.LIGHT_LUX: LIGHT_LUX,
    hc.MASS_KILOGRAMS: UnitOfMass.KILOGRAMS,
    hc.PERCENTAGE: PERCENTAGE,
    hc.POWER_WATT: UnitOfPower.WATT,
    hc.PRESSURE_HPA: UnitOfPressure.HPA,
    hc.REACTIVE_POWER: UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    hc.SIGNAL_STRENGTH_DECIBELS: SIGNAL_STRENGTH_DECIBELS,
    hc.SIGNAL_STRENGTH_DECIBELS_MILLIWATT: SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    hc.SPEED_KILOMETERS_PER_HOUR: UnitOfSpeed.KILOMETERS_PER_HOUR,
    hc.SPEED_METERS_PER_SECOND: UnitOfSpeed.METERS_PER_SECOND,
    hc.SPEED_MILES_PER_HOUR: UnitOfSpeed.MILES_PER_HOUR,
    hc.TEMP_CELSIUS: UnitOfTemperature.CELSIUS,
    hc.TEMP_FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
    hc.TEMP_KELVIN: UnitOfTemperature.KELVIN,
    hc.VOLT: UnitOfElectricPotential.VOLT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tasmota sensor dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota sensor."""
        async_add_entities(
            [
                TasmotaSensor(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(sensor.DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(sensor.DOMAIN),
            async_discover,
        )
    )


class TasmotaSensor(TasmotaAvailability, TasmotaDiscoveryUpdate, SensorEntity):
    """Representation of a Tasmota sensor."""

    _tasmota_entity: tasmota_sensor.TasmotaSensor

    def __init__(self, **kwds: Any) -> None:
        """Initialize the Tasmota sensor."""
        self._state: Any | None = None
        self._state_timestamp: datetime | None = None

        super().__init__(
            **kwds,
        )

        class_or_icon = SENSOR_DEVICE_CLASS_ICON_MAP.get(
            self._tasmota_entity.quantity, {}
        )
        self._attr_device_class = class_or_icon.get(DEVICE_CLASS)
        self._attr_state_class = class_or_icon.get(STATE_CLASS)
        if self._tasmota_entity.quantity in status_sensor.SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        # Hide fast changing status sensors
        if self._tasmota_entity.quantity in (
            hc.SENSOR_STATUS_IP,
            hc.SENSOR_STATUS_RSSI,
            hc.SENSOR_STATUS_SIGNAL,
            hc.SENSOR_STATUS_VERSION,
        ):
            self._attr_entity_registry_enabled_default = False
        self._attr_icon = class_or_icon.get(ICON)
        self._attr_native_unit_of_measurement = SENSOR_UNIT_MAP.get(
            self._tasmota_entity.unit, self._tasmota_entity.unit
        )
        if (
            self._attr_device_class is None
            and self._attr_state_class is None
            and self._attr_native_unit_of_measurement is None
        ):
            # If the sensor has a numeric value, but we couldn't detect what it is,
            # set state class to measurement.
            if self._tasmota_entity.discovered_as_numeric:
                self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.sensor_state_updated)
        await super().async_added_to_hass()

    @callback
    def sensor_state_updated(self, state: Any, **kwargs: Any) -> None:
        """Handle state updates."""
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            self._state_timestamp = state
        else:
            self._state = state
        self.async_write_ha_state()

    @property
    def native_value(self) -> datetime | str | None:
        """Return the state of the entity."""
        if self._state_timestamp and self.device_class == SensorDeviceClass.TIMESTAMP:
            return self._state_timestamp
        return self._state
