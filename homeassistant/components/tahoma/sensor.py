"""Support for TaHoma sensors."""
import logging
from typing import Optional

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    VOLT,
    VOLUME_CUBIC_METERS,
    VOLUME_LITERS,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .tahoma_device import TahomaDevice

_LOGGER = logging.getLogger(__name__)

CORE_CO2_CONCENTRATION_STATE = "core:CO2ConcentrationState"
CORE_CO_CONCENTRATION_STATE = "core:COConcentrationState"
CORE_ELECTRIC_ENERGY_CONSUMPTION_STATE = "core:ElectricEnergyConsumptionState"
CORE_ELECTRIC_POWER_CONSUMPTION_STATE = "core:ElectricPowerConsumptionState"
CORE_FOSSIL_ENERGY_CONSUMPTION_STATE = "core:FossilEnergyConsumptionState"
CORE_GAS_CONSUMPTION_STATE = "core:GasConsumptionState"
CORE_LUMINANCE_STATE = "core:LuminanceState"
CORE_MEASURED_VALUE_TYPE = "core:MeasuredValueType"
CORE_RELATIVE_HUMIDITY_STATE = "core:RelativeHumidityState"
CORE_SUN_ENERGY_STATE = "core:SunEnergyState"
CORE_TEMPERATURE_STATE = "core:TemperatureState"
CORE_THERMAL_ENERGY_CONSUMPTION_STATE = "core:ThermalEnergyConsumptionState"
CORE_WATER_CONSUMPTION_STATE = "core:WaterConsumptionState"
CORE_WINDSPEED_STATE = "core:WindSpeedState"

DEVICE_CLASS_CO = "co"
DEVICE_CLASS_CO2 = "co2"
DEVICE_CLASS_SUN_ENERGY = "sun_energy"
DEVICE_CLASS_WIND_SPEED = "wind_speed"

ICON_AIR_FILTER = "mdi:air-filter"
ICON_PERIODIC_TABLE_CO2 = "mdi:periodic-table-co2"
ICON_SOLAR_POWER = "mdi:solar-power"
ICON_WEATHER_WINDY = "mdi:weather-windy"

UNIT_LX = "lx"

TAHOMA_SENSOR_DEVICE_CLASSES = {
    "CO2Sensor": DEVICE_CLASS_CO2,
    "COSensor": DEVICE_CLASS_CO,
    "ElectricitySensor": DEVICE_CLASS_POWER,
    "HumiditySensor": DEVICE_CLASS_HUMIDITY,
    "LightSensor": DEVICE_CLASS_ILLUMINANCE,
    "RelativeHumiditySensor": DEVICE_CLASS_HUMIDITY,
    "SunSensor": DEVICE_CLASS_SUN_ENERGY,
    "TemperatureSensor": DEVICE_CLASS_TEMPERATURE,
    "WindSensor": DEVICE_CLASS_WIND_SPEED,
}
# From https://www.tahomalink.com/enduser-mobile-web/steer-html5-client/tahoma/bootstrap.js
UNITS = {
    "core:TemperatureInCelcius": TEMP_CELSIUS,
    "core:TemperatureInCelsius": TEMP_CELSIUS,
    "core:TemperatureInKelvin": TEMP_KELVIN,
    "core:TemperatureInFahrenheit": TEMP_FAHRENHEIT,
    "core:LuminanceInLux": UNIT_LX,
    "core:ElectricCurrentInAmpere": ELECTRICAL_CURRENT_AMPERE,
    "core:VoltageInVolt": VOLT,
    "core:ElectricalEnergyInWh": ENERGY_WATT_HOUR,
    "core:ElectricalEnergyInKWh": ENERGY_KILO_WATT_HOUR,
    "core:ElectricalEnergyInMWh": f"M{ENERGY_WATT_HOUR}",
    "core:ElectricalPowerInW": POWER_WATT,
    "core:ElectricalPowerInKW": POWER_KILO_WATT,
    "core:ElectricalPowerInMW": f"M{POWER_WATT}",
    "core:FlowInMeterCubePerHour": VOLUME_CUBIC_METERS,
    "core:LinearSpeedInMeterPerSecond": SPEED_METERS_PER_SECOND,
    "core:RelativeValueInPercentage": PERCENTAGE,
    "core:VolumeInCubicMeter": VOLUME_CUBIC_METERS,
    "core:VolumeInLiter": VOLUME_LITERS,
    "core:FossilEnergyInWh": ENERGY_WATT_HOUR,
    "core:FossilEnergyInKWh": ENERGY_KILO_WATT_HOUR,
    "core:FossilEnergyInMWh": f"M{ENERGY_WATT_HOUR}",
    "meters_seconds": SPEED_METERS_PER_SECOND,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        TahomaSensor(device.deviceurl, coordinator)
        for device in data["entities"].get(SENSOR)
        if device.states
    ]

    async_add_entities(entities)


class TahomaSensor(TahomaDevice, Entity):
    """Representation of a TaHoma Sensor."""

    @property
    def state(self):
        """Return the value of the sensor."""
        state = self.select_state(
            CORE_CO2_CONCENTRATION_STATE,
            CORE_CO_CONCENTRATION_STATE,
            CORE_ELECTRIC_ENERGY_CONSUMPTION_STATE,
            CORE_ELECTRIC_POWER_CONSUMPTION_STATE,
            CORE_FOSSIL_ENERGY_CONSUMPTION_STATE,
            CORE_GAS_CONSUMPTION_STATE,
            CORE_LUMINANCE_STATE,
            CORE_RELATIVE_HUMIDITY_STATE,
            CORE_SUN_ENERGY_STATE,
            CORE_TEMPERATURE_STATE,
            CORE_THERMAL_ENERGY_CONSUMPTION_STATE,
            CORE_WINDSPEED_STATE,
            CORE_WATER_CONSUMPTION_STATE,
        )
        return round(state, 2) if state else None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.device.attributes:
            attribute = self.device.attributes[CORE_MEASURED_VALUE_TYPE]
            return UNITS.get(attribute.value)
        return None

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        icons = {
            DEVICE_CLASS_CO: ICON_AIR_FILTER,
            DEVICE_CLASS_CO2: ICON_PERIODIC_TABLE_CO2,
            DEVICE_CLASS_WIND_SPEED: ICON_WEATHER_WINDY,
            DEVICE_CLASS_SUN_ENERGY: ICON_SOLAR_POWER,
        }

        return icons.get(self.device_class)

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of this entity if any."""
        return TAHOMA_SENSOR_DEVICE_CLASSES.get(
            self.device.widget
        ) or TAHOMA_SENSOR_DEVICE_CLASSES.get(self.device.ui_class)
