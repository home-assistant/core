"""Support for Homekit sensors."""
from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_AQI,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_NITROGEN_DIOXIDE,
    DEVICE_CLASS_OZONE,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SULPHUR_DIOXIDE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, CharacteristicEntity, HomeKitEntity

HUMIDITY_ICON = "mdi:water-percent"
TEMP_C_ICON = "mdi:thermometer"
BRIGHTNESS_ICON = "mdi:brightness-6"
CO2_ICON = "mdi:molecule-co2"


SIMPLE_SENSOR = {
    CharacteristicsTypes.Vendor.EVE_ENERGY_WATT: {
        "name": "Real Time Energy",
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": POWER_WATT,
    },
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY: {
        "name": "Real Time Energy",
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": POWER_WATT,
    },
    CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY_2: {
        "name": "Real Time Energy",
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": POWER_WATT,
    },
    CharacteristicsTypes.Vendor.EVE_DEGREE_AIR_PRESSURE: {
        "name": "Air Pressure",
        "device_class": DEVICE_CLASS_PRESSURE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": PRESSURE_HPA,
    },
    CharacteristicsTypes.TEMPERATURE_CURRENT: {
        "name": "Current Temperature",
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": TEMP_CELSIUS,
        # This sensor is only for temperature characteristics that are not part
        # of a temperature sensor service.
        "probe": lambda char: char.service.type
        != ServicesTypes.get_uuid(ServicesTypes.TEMPERATURE_SENSOR),
    },
    CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: {
        "name": "Current Humidity",
        "device_class": DEVICE_CLASS_HUMIDITY,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": PERCENTAGE,
        # This sensor is only for humidity characteristics that are not part
        # of a humidity sensor service.
        "probe": lambda char: char.service.type
        != ServicesTypes.get_uuid(ServicesTypes.HUMIDITY_SENSOR),
    },
    CharacteristicsTypes.AIR_QUALITY: {
        "name": "Air Quality",
        "device_class": DEVICE_CLASS_AQI,
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    CharacteristicsTypes.DENSITY_PM25: {
        "name": "PM2.5 Density",
        "device_class": DEVICE_CLASS_PM25,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    CharacteristicsTypes.DENSITY_PM10: {
        "name": "PM10 Density",
        "device_class": DEVICE_CLASS_PM10,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    CharacteristicsTypes.DENSITY_OZONE: {
        "name": "Ozone Density",
        "device_class": DEVICE_CLASS_OZONE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    CharacteristicsTypes.DENSITY_NO2: {
        "name": "Nitrogen Dioxide Density",
        "device_class": DEVICE_CLASS_NITROGEN_DIOXIDE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    CharacteristicsTypes.DENSITY_SO2: {
        "name": "Sulphur Dioxide Density",
        "device_class": DEVICE_CLASS_SULPHUR_DIOXIDE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    CharacteristicsTypes.DENSITY_VOC: {
        "name": "Volatile Organic Compound Density",
        "device_class": DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        "state_class": STATE_CLASS_MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
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

    _attr_device_class = DEVICE_CLASS_HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Humidity"

    @property
    def icon(self):
        """Return the sensor icon."""
        return HUMIDITY_ICON

    @property
    def native_value(self):
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)


class HomeKitTemperatureSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit temperature sensor."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.TEMPERATURE_CURRENT]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Temperature"

    @property
    def icon(self):
        """Return the sensor icon."""
        return TEMP_C_ICON

    @property
    def native_value(self):
        """Return the current temperature in Celsius."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)


class HomeKitLightSensor(HomeKitEntity, SensorEntity):
    """Representation of a Homekit light level sensor."""

    _attr_device_class = DEVICE_CLASS_ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LIGHT_LEVEL_CURRENT]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Light Level"

    @property
    def icon(self):
        """Return the sensor icon."""
        return BRIGHTNESS_ICON

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

    _attr_device_class = DEVICE_CLASS_BATTERY
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

    def __init__(
        self,
        conn,
        info,
        char,
        device_class=None,
        state_class=None,
        unit=None,
        icon=None,
        name=None,
        **kwargs,
    ):
        """Initialise a secondary HomeKit characteristic sensor."""
        self._device_class = device_class
        self._state_class = state_class
        self._unit = unit
        self._icon = icon
        self._name = name

        super().__init__(conn, info, char)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def device_class(self):
        """Return type of sensor."""
        return self._device_class

    @property
    def state_class(self):
        """Return type of state."""
        return self._state_class

    @property
    def native_unit_of_measurement(self):
        """Return units for the sensor."""
        return self._unit

    @property
    def icon(self):
        """Return the sensor icon."""
        return self._icon

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{super().name} - {self._name}"

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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit sensors."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service):
        entity_class = ENTITY_TYPES.get(service.short_type)
        if not entity_class:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)

    @callback
    def async_add_characteristic(char: Characteristic):
        kwargs = SIMPLE_SENSOR.get(char.type)
        if not kwargs:
            return False
        if "probe" in kwargs and not kwargs["probe"](char):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        async_add_entities([SimpleSensor(conn, info, char, **kwargs)], True)

        return True

    conn.add_char_factory(async_add_characteristic)
