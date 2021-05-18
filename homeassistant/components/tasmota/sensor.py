"""Support for Tasmota sensors."""
from __future__ import annotations

from hatasmota import const as hc, status_sensor

from homeassistant.components import sensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
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
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

DEVICE_CLASS = "device_class"
ICON = "icon"

# A Tasmota sensor type may be mapped to either a device class or an icon, not both
SENSOR_DEVICE_CLASS_ICON_MAP = {
    hc.SENSOR_AMBIENT: {DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE},
    hc.SENSOR_APPARENT_POWERUSAGE: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    hc.SENSOR_BATTERY: {DEVICE_CLASS: DEVICE_CLASS_BATTERY},
    hc.SENSOR_CCT: {ICON: "mdi:temperature-kelvin"},
    hc.SENSOR_CO2: {DEVICE_CLASS: DEVICE_CLASS_CO2},
    hc.SENSOR_COLOR_BLUE: {ICON: "mdi:palette"},
    hc.SENSOR_COLOR_GREEN: {ICON: "mdi:palette"},
    hc.SENSOR_COLOR_RED: {ICON: "mdi:palette"},
    hc.SENSOR_CURRENT: {ICON: "mdi:alpha-a-circle-outline"},
    hc.SENSOR_DEWPOINT: {ICON: "mdi:weather-rainy"},
    hc.SENSOR_DISTANCE: {ICON: "mdi:leak"},
    hc.SENSOR_ECO2: {ICON: "mdi:molecule-co2"},
    hc.SENSOR_FREQUENCY: {ICON: "mdi:current-ac"},
    hc.SENSOR_HUMIDITY: {DEVICE_CLASS: DEVICE_CLASS_HUMIDITY},
    hc.SENSOR_ILLUMINANCE: {DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE},
    hc.SENSOR_STATUS_IP: {ICON: "mdi:ip-network"},
    hc.SENSOR_STATUS_LINK_COUNT: {ICON: "mdi:counter"},
    hc.SENSOR_MOISTURE: {ICON: "mdi:cup-water"},
    hc.SENSOR_STATUS_MQTT_COUNT: {ICON: "mdi:counter"},
    hc.SENSOR_PB0_3: {ICON: "mdi:flask"},
    hc.SENSOR_PB0_5: {ICON: "mdi:flask"},
    hc.SENSOR_PB10: {ICON: "mdi:flask"},
    hc.SENSOR_PB1: {ICON: "mdi:flask"},
    hc.SENSOR_PB2_5: {ICON: "mdi:flask"},
    hc.SENSOR_PB5: {ICON: "mdi:flask"},
    hc.SENSOR_PM10: {ICON: "mdi:air-filter"},
    hc.SENSOR_PM1: {ICON: "mdi:air-filter"},
    hc.SENSOR_PM2_5: {ICON: "mdi:air-filter"},
    hc.SENSOR_POWERFACTOR: {ICON: "mdi:alpha-f-circle-outline"},
    hc.SENSOR_POWERUSAGE: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    hc.SENSOR_PRESSURE: {DEVICE_CLASS: DEVICE_CLASS_PRESSURE},
    hc.SENSOR_PRESSUREATSEALEVEL: {DEVICE_CLASS: DEVICE_CLASS_PRESSURE},
    hc.SENSOR_PROXIMITY: {ICON: "mdi:ruler"},
    hc.SENSOR_REACTIVE_POWERUSAGE: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    hc.SENSOR_STATUS_LAST_RESTART_TIME: {DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP},
    hc.SENSOR_STATUS_RESTART_REASON: {ICON: "mdi:information-outline"},
    hc.SENSOR_STATUS_SIGNAL: {DEVICE_CLASS: DEVICE_CLASS_SIGNAL_STRENGTH},
    hc.SENSOR_STATUS_RSSI: {ICON: "mdi:access-point"},
    hc.SENSOR_STATUS_SSID: {ICON: "mdi:access-point-network"},
    hc.SENSOR_TEMPERATURE: {DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE},
    hc.SENSOR_TODAY: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    hc.SENSOR_TOTAL: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    hc.SENSOR_TOTAL_START_TIME: {ICON: "mdi:progress-clock"},
    hc.SENSOR_TVOC: {ICON: "mdi:air-filter"},
    hc.SENSOR_VOLTAGE: {ICON: "mdi:alpha-v-circle-outline"},
    hc.SENSOR_WEIGHT: {ICON: "mdi:scale"},
    hc.SENSOR_YESTERDAY: {DEVICE_CLASS: DEVICE_CLASS_POWER},
}

SENSOR_UNIT_MAP = {
    hc.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    hc.CONCENTRATION_PARTS_PER_BILLION: CONCENTRATION_PARTS_PER_BILLION,
    hc.CONCENTRATION_PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    hc.ELECTRICAL_CURRENT_AMPERE: ELECTRICAL_CURRENT_AMPERE,
    hc.ELECTRICAL_VOLT_AMPERE: ELECTRICAL_VOLT_AMPERE,
    hc.ENERGY_KILO_WATT_HOUR: ENERGY_KILO_WATT_HOUR,
    hc.FREQUENCY_HERTZ: FREQUENCY_HERTZ,
    hc.LENGTH_CENTIMETERS: LENGTH_CENTIMETERS,
    hc.LIGHT_LUX: LIGHT_LUX,
    hc.MASS_KILOGRAMS: MASS_KILOGRAMS,
    hc.PERCENTAGE: PERCENTAGE,
    hc.POWER_WATT: POWER_WATT,
    hc.PRESSURE_HPA: PRESSURE_HPA,
    hc.SIGNAL_STRENGTH_DECIBELS: SIGNAL_STRENGTH_DECIBELS,
    hc.SIGNAL_STRENGTH_DECIBELS_MILLIWATT: SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    hc.SPEED_KILOMETERS_PER_HOUR: SPEED_KILOMETERS_PER_HOUR,
    hc.SPEED_METERS_PER_SECOND: SPEED_METERS_PER_SECOND,
    hc.SPEED_MILES_PER_HOUR: SPEED_MILES_PER_HOUR,
    hc.TEMP_CELSIUS: TEMP_CELSIUS,
    hc.TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
    hc.TEMP_KELVIN: TEMP_KELVIN,
    hc.VOLT: VOLT,
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
        TASMOTA_DISCOVERY_ENTITY_NEW.format(sensor.DOMAIN),
        async_discover_sensor,
    )


class TasmotaSensor(TasmotaAvailability, TasmotaDiscoveryUpdate, SensorEntity):
    """Representation of a Tasmota sensor."""

    def __init__(self, **kwds):
        """Initialize the Tasmota sensor."""
        self._state = None

        super().__init__(
            **kwds,
        )

    @callback
    def state_updated(self, state, **kwargs):
        """Handle state updates."""
        self._state = state
        self.async_write_ha_state()

    @property
    def device_class(self) -> str | None:
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
    def force_update(self):
        """Force update."""
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return SENSOR_UNIT_MAP.get(self._tasmota_entity.unit, self._tasmota_entity.unit)
