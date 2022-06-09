"""Support for Homekit sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNOWN_DEVICES, CharacteristicEntity, HomeKitEntity
from .connection import HKDevice

CO2_ICON = "mdi:molecule-co2"


@dataclass
class HomeKitSensorEntityDescription(SensorEntityDescription):
    """Describes Homekit sensor."""

    probe: Callable[[Characteristic], bool] | None = None


SIMPLE_SENSOR: dict[str, HomeKitSensorEntityDescription] = {
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_WATT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_WATT,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS,
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS_20: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_AMPS_20,
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_KW_HOUR: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_CONNECTSENSE_ENERGY_KW_HOUR,
        name="Energy kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_WATT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_WATT,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_KW_HOUR: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_KW_HOUR,
        name="Energy kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_VOLTAGE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_VOLTAGE,
        name="Volts",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    ),
    CharacteristicsTypes.VENDOR_EVE_ENERGY_AMPERE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_ENERGY_AMPERE,
        name="Amps",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY_2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_KOOGEEK_REALTIME_ENERGY_2,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.VENDOR_EVE_DEGREE_AIR_PRESSURE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_DEGREE_AIR_PRESSURE,
        name="Air Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRESSURE_HPA,
    ),
    CharacteristicsTypes.VENDOR_VOCOLINC_OUTLET_ENERGY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.VENDOR_VOCOLINC_OUTLET_ENERGY,
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.TEMPERATURE_CURRENT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.TEMPERATURE_CURRENT,
        name="Current Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        # This sensor is only for temperature characteristics that are not part
        # of a temperature sensor service.
        probe=(lambda char: char.service.type != ServicesTypes.TEMPERATURE_SENSOR),
    ),
    CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
        name="Current Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        # This sensor is only for humidity characteristics that are not part
        # of a humidity sensor service.
        probe=(lambda char: char.service.type != ServicesTypes.HUMIDITY_SENSOR),
    ),
    CharacteristicsTypes.AIR_QUALITY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.AIR_QUALITY,
        name="Air Quality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CharacteristicsTypes.DENSITY_PM25: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_PM25,
        name="PM2.5 Density",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_PM10: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_PM10,
        name="PM10 Density",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_OZONE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_OZONE,
        name="Ozone Density",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_NO2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_NO2,
        name="Nitrogen Dioxide Density",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_SO2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_SO2,
        name="Sulphur Dioxide Density",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CharacteristicsTypes.DENSITY_VOC: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.DENSITY_VOC,
        name="Volatile Organic Compound Density",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
}


class HomeKitHumiditySensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{super().name} Humidity"

    @property
    def native_value(self) -> float:
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)


class HomeKitTemperatureSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.TEMPERATURE_CURRENT]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{super().name} Temperature"

    @property
    def native_value(self) -> float:
        """Return the current temperature in Celsius."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)


class HomeKitLightSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit light level sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LIGHT_LEVEL_CURRENT]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{super().name} Light Level"

    @property
    def native_value(self) -> int:
        """Return the current light level in lux."""
        return self.service.value(CharacteristicsTypes.LIGHT_LEVEL_CURRENT)


class HomeKitCarbonDioxideSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit Carbon Dioxide sensor."""

    _attr_icon = CO2_ICON
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_DIOXIDE_LEVEL]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{super().name} CO2"

    @property
    def native_value(self) -> int:
        """Return the current CO2 level in ppm."""
        return self.service.value(CharacteristicsTypes.CARBON_DIOXIDE_LEVEL)


class HomeKitBatterySensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [
            CharacteristicsTypes.BATTERY_LEVEL,
            CharacteristicsTypes.STATUS_LO_BATT,
            CharacteristicsTypes.CHARGING_STATE,
        ]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{super().name} Battery"

    @property
    def icon(self) -> str:
        """Return the sensor icon."""
        if not self.available or self.state is None:
            return "mdi:battery-unknown"

        # This is similar to the logic in helpers.icon, but we have delegated the
        # decision about what mdi:battery-alert is to the device.
        icon = "mdi:battery"
        if self.is_charging and self.state > 10:
            percentage = int(round(self.state / 20 - 0.01)) * 20
            icon += f"-charging-{percentage}"
        elif self.is_charging:
            icon += "-outline"
        elif self.is_low_battery:
            icon += "-alert"
        elif self.state < 95:
            percentage = max(int(round(self.state / 10 - 0.01)) * 10, 10)
            icon += f"-{percentage}"

        return icon

    @property
    def is_low_battery(self) -> bool:
        """Return true if battery level is low."""
        return self.service.value(CharacteristicsTypes.STATUS_LO_BATT) == 1

    @property
    def is_charging(self) -> bool:
        """Return true if currently charing."""
        # 0 = not charging
        # 1 = charging
        # 2 = not chargeable
        return self.service.value(CharacteristicsTypes.CHARGING_STATE) == 1

    @property
    def native_value(self) -> int:
        """Return the current battery level percentage."""
        return self.service.value(CharacteristicsTypes.BATTERY_LEVEL)


class SimpleSensor(CharacteristicEntity, SensorEntity):
    """
    A simple sensor for a single characteristic.

    This may be an additional secondary entity that is part of another service. An
    example is a switch that has an energy sensor.

    These *have* to have a different unique_id to the normal sensors as there could
    be multiple entities per HomeKit service (this was not previously the case).
    """

    entity_description: HomeKitSensorEntityDescription

    def __init__(
        self,
        conn: HKDevice,
        info: ConfigType,
        char: Characteristic,
        description: HomeKitSensorEntityDescription,
    ) -> None:
        """Initialise a secondary HomeKit characteristic sensor."""
        self.entity_description = description
        super().__init__(conn, info, char)

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{super().name} {self.entity_description.name}"

    @property
    def native_value(self) -> str | int | float:
        """Return the current sensor value."""
        return self._char.value


ENTITY_TYPES = {
    ServicesTypes.HUMIDITY_SENSOR: HomeKitHumiditySensor,
    ServicesTypes.TEMPERATURE_SENSOR: HomeKitTemperatureSensor,
    ServicesTypes.LIGHT_SENSOR: HomeKitLightSensor,
    ServicesTypes.CARBON_DIOXIDE_SENSOR: HomeKitCarbonDioxideSensor,
    ServicesTypes.BATTERY_SERVICE: HomeKitBatterySensor,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit sensors."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if not (entity_class := ENTITY_TYPES.get(service.type)):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        if not (description := SIMPLE_SENSOR.get(char.type)):
            return False
        if description.probe and not description.probe(char):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        async_add_entities([SimpleSensor(conn, info, char, description)], True)

        return True

    conn.add_char_factory(async_add_characteristic)
