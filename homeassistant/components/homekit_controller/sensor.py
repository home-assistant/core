"""Support for Homekit sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

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
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES, CharacteristicEntity, HomeKitEntity

CO2_ICON = "mdi:molecule-co2"


@dataclass
class HomeKitSensorEntityDescription(SensorEntityDescription):
    """Describes Homekit sensor."""

    probe: Callable[[Characteristic], bool] | None = None


SIMPLE_SENSOR: dict[str, HomeKitSensorEntityDescription] = {
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_WATT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_WATT,
        name="Real Time Energy",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_AMPS: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_AMPS,
        name="Real Time Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_AMPS_20: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_AMPS_20,
        name="Real Time Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_KW_HOUR: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.CONNECTSENSE_ENERGY_KW_HOUR,
        name="Energy kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    ),
    CharacteristicsTypes.Vendor.EVE_ENERGY_WATT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.EVE_ENERGY_WATT,
        name="Real Time Energy",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY,
        name="Real Time Energy",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY_2: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY_2,
        name="Real Time Energy",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    ),
    CharacteristicsTypes.Vendor.EVE_DEGREE_AIR_PRESSURE: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.EVE_DEGREE_AIR_PRESSURE,
        name="Air Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRESSURE_HPA,
    ),
    CharacteristicsTypes.Vendor.VOCOLINC_OUTLET_ENERGY: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.Vendor.VOCOLINC_OUTLET_ENERGY,
        name="Real Time Energy",
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
        probe=(
            lambda char: char.service.type
            != ServicesTypes.get_uuid(ServicesTypes.TEMPERATURE_SENSOR)
        ),
    ),
    CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: HomeKitSensorEntityDescription(
        key=CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
        name="Current Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        # This sensor is only for humidity characteristics that are not part
        # of a humidity sensor service.
        probe=(
            lambda char: char.service.type
            != ServicesTypes.get_uuid(ServicesTypes.HUMIDITY_SENSOR)
        ),
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

# For legacy reasons, "built-in" characteristic types are in their short form
# And vendor types don't have a short form
# This means long and short forms get mixed up in this dict, and comparisons
# don't work!
# We call get_uuid on *every* type to normalise them to the long form
# Eventually aiohomekit will use the long form exclusively amd this can be removed.
for k, v in list(SIMPLE_SENSOR.items()):
    SIMPLE_SENSOR[CharacteristicsTypes.get_uuid(k)] = SIMPLE_SENSOR.pop(k)


class HomeKitHumiditySensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Humidity"

    @property
    def native_value(self):
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)


class HomeKitTemperatureSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.TEMPERATURE_CURRENT]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Temperature"

    @property
    def native_value(self):
        """Return the current temperature in Celsius."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)


class HomeKitLightSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit light level sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LIGHT_LEVEL_CURRENT]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Light Level"

    @property
    def native_value(self):
        """Return the current light level in lux."""
        return self.service.value(CharacteristicsTypes.LIGHT_LEVEL_CURRENT)


class HomeKitCarbonDioxideSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit Carbon Dioxide sensor."""

    _attr_icon = CO2_ICON
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_DIOXIDE_LEVEL]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} CO2"

    @property
    def native_value(self):
        """Return the current CO2 level in ppm."""
        return self.service.value(CharacteristicsTypes.CARBON_DIOXIDE_LEVEL)


class HomeKitBatterySensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [
            CharacteristicsTypes.BATTERY_LEVEL,
            CharacteristicsTypes.STATUS_LO_BATT,
            CharacteristicsTypes.CHARGING_STATE,
        ]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Battery"

    @property
    def icon(self):
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
    def is_low_battery(self):
        """Return true if battery level is low."""
        return self.service.value(CharacteristicsTypes.STATUS_LO_BATT) == 1

    @property
    def is_charging(self):
        """Return true if currently charing."""
        # 0 = not charging
        # 1 = charging
        # 2 = not chargeable
        return self.service.value(CharacteristicsTypes.CHARGING_STATE) == 1

    @property
    def native_value(self):
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
        conn,
        info,
        char,
        description: HomeKitSensorEntityDescription,
    ):
        """Initialise a secondary HomeKit characteristic sensor."""
        self.entity_description = description
        super().__init__(conn, info, char)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{super().name} {self.entity_description.name}"

    @property
    def native_value(self):
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
    def async_add_service(service):
        if not (entity_class := ENTITY_TYPES.get(service.short_type)):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)

    @callback
    def async_add_characteristic(char: Characteristic):
        if not (description := SIMPLE_SENSOR.get(char.type)):
            return False
        if description.probe and not description.probe(char):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        async_add_entities([SimpleSensor(conn, info, char, description)], True)

        return True

    conn.add_char_factory(async_add_characteristic)
