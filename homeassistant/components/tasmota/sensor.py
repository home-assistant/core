"""Support for Tasmota sensors."""
from typing import Optional

from hatasmota import status_sensor
from hatasmota.const import (
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
    SENSOR_STATUS_SIGNAL,
    SENSOR_TEMPERATURE,
    SENSOR_TODAY,
    SENSOR_TOTAL,
    SENSOR_TOTAL_START_TIME,
    SENSOR_TVOC,
    SENSOR_VOLTAGE,
    SENSOR_WEIGHT,
    SENSOR_YESTERDAY,
)

from homeassistant.components import sensor
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
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
    SENSOR_MOISTURE: {ICON: "mdi:cup-water"},
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
    SENSOR_STATUS_SIGNAL: {DEVICE_CLASS: DEVICE_CLASS_SIGNAL_STRENGTH},
    SENSOR_TEMPERATURE: {DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE},
    SENSOR_TODAY: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_TOTAL: {DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_TOTAL_START_TIME: {ICON: "mdi:progress-clock"},
    SENSOR_TVOC: {ICON: "mdi:air-filter"},
    SENSOR_VOLTAGE: {ICON: "mdi:alpha-v-circle-outline"},
    SENSOR_WEIGHT: {ICON: "mdi:scale"},
    SENSOR_YESTERDAY: {DEVICE_CLASS: DEVICE_CLASS_POWER},
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
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._tasmota_entity.unit
