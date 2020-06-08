"""Support for the Subaru sensors."""
import logging

import subarulink.const as sc

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    TEMP_CELSIUS,
    TIME_MINUTES,
    UNIT_PERCENTAGE,
    VOLT,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.util.distance import convert as dist_convert
from homeassistant.util.unit_system import (
    IMPERIAL_SYSTEM,
    LENGTH_UNITS,
    TEMPERATURE_UNITS,
)
from homeassistant.util.volume import convert as vol_convert

from . import DOMAIN as SUBARU_DOMAIN, SubaruEntity

_LOGGER = logging.getLogger(__name__)
L_PER_GAL = vol_convert(1, VOLUME_GALLONS, VOLUME_LITERS)
KM_PER_MI = dist_convert(1, LENGTH_MILES, LENGTH_KILOMETERS)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Subaru sensors by config_entry."""
    coordinator = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["coordinator"]
    vehicle_info = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["vehicles"]
    entities = []
    for vin in vehicle_info.keys():
        _create_sensor_entities(entities, vehicle_info[vin], coordinator, hass)
    async_add_entities(entities, True)


def _create_sensor_entities(entities, vehicle_info, coordinator, hass):

    if vehicle_info["is_ev"]:
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                "EV Range",
                sc.EV_DISTANCE_TO_EMPTY,
                LENGTH_MILES,
            )
        )
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                "EV Battery Level",
                sc.EV_STATE_OF_CHARGE_PERCENT,
                UNIT_PERCENTAGE,
            )
        )
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                "EV Time to Full Charge",
                sc.EV_TIME_TO_FULLY_CHARGED,
                TIME_MINUTES,
            )
        )

    if vehicle_info["api_gen"] == "g2":
        entities.append(FuelEconomySensor(vehicle_info, coordinator, hass))
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                "12V Battery Voltage",
                sc.BATTERY_VOLTAGE,
                VOLT,
            )
        )
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                "Range",
                sc.DIST_TO_EMPTY,
                LENGTH_KILOMETERS,
            )
        )
        entities.append(
            SubaruSensor(
                vehicle_info, coordinator, hass, "Odometer", sc.ODOMETER, LENGTH_METERS
            )
        )
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                "External Temp",
                sc.EXTERNAL_TEMP,
                TEMP_CELSIUS,
            )
        )


class SubaruSensor(SubaruEntity):
    """Class for Subaru sensors."""

    def __init__(self, vehicle_info, coordinator, hass, title, data_field, api_unit):
        """Initialize the sensor."""
        super().__init__(vehicle_info, coordinator)
        self.hass_type = "sensor"
        self.current_value = None
        self.hass = hass
        self.title = title
        self.data_field = data_field
        self.api_unit = api_unit

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.current_value is None:
            return None

        if self.api_unit in TEMPERATURE_UNITS:
            return round(
                self.hass.config.units.temperature(self.current_value, self.api_unit), 1
            )

        if self.api_unit in LENGTH_UNITS:
            return round(
                self.hass.config.units.length(self.current_value, self.api_unit), 1
            )

        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        if self.api_unit in TEMPERATURE_UNITS:
            return self.hass.config.units.temperature_unit

        if self.api_unit in LENGTH_UNITS:
            return self.hass.config.units.length_unit

        return self.api_unit

    async def async_update(self):
        """Update the state from the sensor."""
        await super().async_update()

        self.current_value = self.coordinator.data[self.vin]["status"][self.data_field]
        if self.current_value in sc.BAD_SENSOR_VALUES:
            self.current_value = None
        if isinstance(self.current_value, str):
            if "." in self.current_value:
                self.current_value = float(self.current_value)
            else:
                self.current_value = int(self.current_value)


class FuelEconomySensor(SubaruSensor):
    """
    Subaru Sensor for fuel economy.

    This SubaruSensor subclass is needed for this sensor for non-standard units and conversions.
    The units provided by the API are: Liters/10km
    """

    def __init__(self, vehicle_info, coordinator, hass):
        """Initialize the sensor."""
        super().__init__(
            vehicle_info,
            coordinator,
            hass,
            "Avg Fuel Consumption",
            sc.AVG_FUEL_CONSUMPTION,
            None,
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.current_value is None:
            return None

        if self.hass.config.units == IMPERIAL_SYSTEM:
            return round((1000.0 * L_PER_GAL) / (KM_PER_MI * self.current_value), 1)

        return self.current_value / 10.0

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        if self.hass.config.units == IMPERIAL_SYSTEM:
            return "mi/gal"

        return "L/100km"
