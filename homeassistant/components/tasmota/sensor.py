"""Support for Tasmota sensors."""
from typing import Optional

from hatasmota import status_sensor
from hatasmota.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER as TASMOTA_CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION as TASMOTA_CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION as TASMOTA_CONCENTRATION_PARTS_PER_MILLION,
    ELECTRICAL_CURRENT_AMPERE as TASMOTA_ELECTRICAL_CURRENT_AMPERE,
    ELECTRICAL_VOLT_AMPERE as TASMOTA_ELECTRICAL_VOLT_AMPERE,
    ENERGY_KILO_WATT_HOUR as TASMOTA_ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ as TASMOTA_FREQUENCY_HERTZ,
    LENGTH_CENTIMETERS as TASMOTA_LENGTH_CENTIMETERS,
    LIGHT_LUX as TASMOTA_LIGHT_LUX,
    MASS_KILOGRAMS as TASMOTA_MASS_KILOGRAMS,
    PERCENTAGE as TASMOTA_PERCENTAGE,
    POWER_WATT as TASMOTA_POWER_WATT,
    PRESSURE_HPA as TASMOTA_PRESSURE_HPA,
    SENSOR_AMBIENT,
    SENSOR_APPARENT_POWERUSAGE,
    SENSOR_BATTERY,
    SENSOR_CCT,
    SENSOR_CO2,
    SENSOR_COLOR_BLUE,
    SENSOR_COLOR_GREEN,
    SENSOR_COLOR_RED,
    SENSOR_CURRENT,
    SENSOR_DEWPOINT,
    SENSOR_DISTANCE,
    SENSOR_ECO2,
    SENSOR_FREQUENCY,
    SENSOR_HUMIDITY,
    SENSOR_ILLUMINANCE,
    SENSOR_MOISTURE,
    SENSOR_PB0_3,
    SENSOR_PB0_5,
    SENSOR_PB1,
    SENSOR_PB2_5,
    SENSOR_PB5,
    SENSOR_PB10,
    SENSOR_PM1,
    SENSOR_PM2_5,
    SENSOR_PM10,
    SENSOR_POWERFACTOR,
    SENSOR_POWERUSAGE,
    SENSOR_PRESSURE,
    SENSOR_PRESSUREATSEALEVEL,
    SENSOR_PROXIMITY,
    SENSOR_REACTIVE_POWERUSAGE,
    SENSOR_STATUS_IP,
    SENSOR_STATUS_LAST_RESTART_TIME,
    SENSOR_STATUS_LINK_COUNT,
    SENSOR_STATUS_MQTT_COUNT,
    SENSOR_STATUS_RESTART_REASON,
    SENSOR_STATUS_RSSI,
    SENSOR_STATUS_SIGNAL,
    SENSOR_STATUS_SSID,
    SENSOR_TEMPERATURE,
    SENSOR_TODAY,
    SENSOR_TOTAL,
    SENSOR_TOTAL_START_TIME,
    SENSOR_TVOC,
    SENSOR_VOLTAGE,
    SENSOR_WEIGHT,
    SENSOR_YESTERDAY,
    SIGNAL_STRENGTH_DECIBELS as TASMOTA_SIGNAL_STRENGTH_DECIBELS,
    SPEED_KILOMETERS_PER_HOUR as TASMOTA_SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND as TASMOTA_SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR as TASMOTA_SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS as TASMOTA_TEMP_CELSIUS,
    TEMP_FAHRENHEIT as TASMOTA_TEMP_FAHRENHEIT,
    TEMP_KELVIN as TASMOTA_TEMP_KELVIN,
    VOLT as TASMOTA_VOLT,
)

from homeassistant.components import sensor
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ELECTRICAL_CURRENT_AMPERE,
    ELECTRICAL_VOLT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_CENTIMETERS,
    LIGHT_LUX,
    MASS_KILOGRAMS,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    VOLT,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DATA_REMOVE_DISCOVER_COMPONENT, DOMAIN as TASMOTA_DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

DEVICE_CLASS = "device_class"
ICON = "icon"

# A Tasmota sensor type may be mapped to either a device class or an icon, not both
SENSOR_DEVICE_CLASS_ICON_MAP = {
    SENSOR_AMBIENT: {DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE},
    SENSOR_APPARENT_POWERUSAGE: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_BATTERY: {DEVICE_CLASS: DEVICE_CLASS_BATTERY},
    SENSOR_CCT: {ICON: "mdi:temperature-kelvin"},
    SENSOR_CO2: {ICON: "mdi:molecule-co2"},
    SENSOR_COLOR_BLUE: {ICON: "mdi:palette"},
    SENSOR_COLOR_GREEN: {ICON: "mdi:palette"},
    SENSOR_COLOR_RED: {ICON: "mdi:palette"},
    SENSOR_CURRENT: {ICON: "mdi:alpha-a-circle-outline"},
    SENSOR_DEWPOINT: {ICON: "mdi:weather-rainy"},
    SENSOR_DISTANCE: {ICON: "mdi:leak"},
    SENSOR_ECO2: {ICON: "mdi:molecule-co2"},
    SENSOR_FREQUENCY: {ICON: "mdi:current-ac"},
    SENSOR_HUMIDITY: {DEVICE_CLASS: DEVICE_CLASS_HUMIDITY},
    SENSOR_ILLUMINANCE: {DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE},
    SENSOR_STATUS_IP: {ICON: "mdi:ip-network"},
    SENSOR_STATUS_LINK_COUNT: {ICON: "mdi:counter"},
    SENSOR_MOISTURE: {ICON: "mdi:cup-water"},
    SENSOR_STATUS_MQTT_COUNT: {ICON: "mdi:counter"},
    SENSOR_PB0_3: {ICON: "mdi:flask"},
    SENSOR_PB0_5: {ICON: "mdi:flask"},
    SENSOR_PB10: {ICON: "mdi:flask"},
    SENSOR_PB1: {ICON: "mdi:flask"},
    SENSOR_PB2_5: {ICON: "mdi:flask"},
    SENSOR_PB5: {ICON: "mdi:flask"},
    SENSOR_PM10: {ICON: "mdi:air-filter"},
    SENSOR_PM1: {ICON: "mdi:air-filter"},
    SENSOR_PM2_5: {ICON: "mdi:air-filter"},
    SENSOR_POWERFACTOR: {ICON: "mdi:alpha-f-circle-outline"},
    SENSOR_POWERUSAGE: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_PRESSURE: {DEVICE_CLASS: DEVICE_CLASS_PRESSURE},
    SENSOR_PRESSUREATSEALEVEL: {DEVICE_CLASS: DEVICE_CLASS_PRESSURE},
    SENSOR_PROXIMITY: {ICON: "mdi:ruler"},
    SENSOR_REACTIVE_POWERUSAGE: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_STATUS_LAST_RESTART_TIME: {DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP},
    SENSOR_STATUS_RESTART_REASON: {ICON: "mdi:information-outline"},
    SENSOR_STATUS_SIGNAL: {DEVICE_CLASS: DEVICE_CLASS_SIGNAL_STRENGTH},
    SENSOR_STATUS_RSSI: {ICON: "mdi:access-point"},
    SENSOR_STATUS_SSID: {ICON: "mdi:access-point-network"},
    SENSOR_TEMPERATURE: {DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE},
    SENSOR_TODAY: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_TOTAL: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_TOTAL_START_TIME: {ICON: "mdi:progress-clock"},
    SENSOR_TVOC: {ICON: "mdi:air-filter"},
    SENSOR_VOLTAGE: {ICON: "mdi:alpha-v-circle-outline"},
    SENSOR_WEIGHT: {ICON: "mdi:scale"},
    SENSOR_YESTERDAY: {DEVICE_CLASS: DEVICE_CLASS_POWER},
}

SENSOR_UNIT_MAP = {
    TASMOTA_CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    TASMOTA_CONCENTRATION_PARTS_PER_BILLION: CONCENTRATION_PARTS_PER_BILLION,
    TASMOTA_CONCENTRATION_PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    TASMOTA_ELECTRICAL_CURRENT_AMPERE: ELECTRICAL_CURRENT_AMPERE,
    TASMOTA_ELECTRICAL_VOLT_AMPERE: ELECTRICAL_VOLT_AMPERE,
    TASMOTA_ENERGY_KILO_WATT_HOUR: ENERGY_KILO_WATT_HOUR,
    TASMOTA_FREQUENCY_HERTZ: FREQUENCY_HERTZ,
    TASMOTA_LENGTH_CENTIMETERS: LENGTH_CENTIMETERS,
    TASMOTA_LIGHT_LUX: LIGHT_LUX,
    TASMOTA_MASS_KILOGRAMS: MASS_KILOGRAMS,
    TASMOTA_PERCENTAGE: PERCENTAGE,
    TASMOTA_POWER_WATT: POWER_WATT,
    TASMOTA_PRESSURE_HPA: PRESSURE_HPA,
    TASMOTA_SIGNAL_STRENGTH_DECIBELS: SIGNAL_STRENGTH_DECIBELS,
    TASMOTA_SPEED_KILOMETERS_PER_HOUR: SPEED_KILOMETERS_PER_HOUR,
    TASMOTA_SPEED_METERS_PER_SECOND: SPEED_METERS_PER_SECOND,
    TASMOTA_SPEED_MILES_PER_HOUR: SPEED_MILES_PER_HOUR,
    TASMOTA_TEMP_CELSIUS: TEMP_CELSIUS,
    TASMOTA_TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
    TASMOTA_TEMP_KELVIN: TEMP_KELVIN,
    TASMOTA_VOLT: VOLT,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota sensor dynamically through discovery."""

    async def async_discover_sensor(tasmota_entity, discovery_hash):
        """Discover and add a Tasmota sensor."""
        async_add_entities(
            [
                TasmotaSensor(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(sensor.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(sensor.DOMAIN, TASMOTA_DOMAIN),
        async_discover_sensor,
    )


class TasmotaSensor(TasmotaAvailability, TasmotaDiscoveryUpdate, Entity):
    """Representation of a Tasmota sensor."""

    def __init__(self, **kwds):
        """Initialize the Tasmota sensor."""
        self._state = None

        super().__init__(
            discovery_update=self.discovery_update,
            **kwds,
        )

    @callback
    def state_updated(self, state, **kwargs):
        """Handle state updates."""
        self._state = state
        self.async_write_ha_state()

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        class_or_icon = SENSOR_DEVICE_CLASS_ICON_MAP.get(
            self._tasmota_entity.quantity, {}
        )
        return class_or_icon.get(DEVICE_CLASS)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # Hide status sensors to not overwhelm users
        if self._tasmota_entity.quantity in status_sensor.SENSORS:
            return False
        return True

    @property
    def icon(self):
        """Return the icon."""
        class_or_icon = SENSOR_DEVICE_CLASS_ICON_MAP.get(
            self._tasmota_entity.quantity, {}
        )
        return class_or_icon.get(ICON)

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state and self.device_class == DEVICE_CLASS_TIMESTAMP:
            return self._state.isoformat()
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return SENSOR_UNIT_MAP.get(self._tasmota_entity.unit, self._tasmota_entity.unit)
