"""Support for Tasmota sensors."""
import logging
from typing import Optional

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
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as TASMOTA_DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

_LOGGER = logging.getLogger(__name__)

SENSOR_DEVICE_CLASS_MAP = {
    SENSOR_AMBIENT: DEVICE_CLASS_ILLUMINANCE,
    SENSOR_APPARENT_POWERUSAGE: DEVICE_CLASS_POWER,
    SENSOR_BATTERY: DEVICE_CLASS_BATTERY,
    SENSOR_HUMIDITY: DEVICE_CLASS_HUMIDITY,
    SENSOR_ILLUMINANCE: DEVICE_CLASS_ILLUMINANCE,
    SENSOR_POWERUSAGE: DEVICE_CLASS_POWER,
    SENSOR_PRESSURE: DEVICE_CLASS_PRESSURE,
    SENSOR_PRESSUREATSEALEVEL: DEVICE_CLASS_PRESSURE,
    SENSOR_REACTIVE_POWERUSAGE: DEVICE_CLASS_POWER,
    SENSOR_TEMPERATURE: DEVICE_CLASS_TEMPERATURE,
    SENSOR_TODAY: DEVICE_CLASS_POWER,
    SENSOR_TOTAL: DEVICE_CLASS_POWER,
    SENSOR_YESTERDAY: DEVICE_CLASS_POWER,
}

SENSOR_ICON_MAP = {
    SENSOR_CCT: "mdi:temperature-kelvin",
    SENSOR_CO2: "mdi:molecule-co2",
    SENSOR_COLOR_BLUE: "mdi:palette",
    SENSOR_COLOR_GREEN: "mdi:palette",
    SENSOR_COLOR_RED: "mdi:palette",
    SENSOR_CURRENT: "mdi:alpha-a-circle-outline",
    SENSOR_DEWPOINT: "mdi:weather-rainy",
    SENSOR_DISTANCE: "mdi:leak",
    SENSOR_ECO2: "mdi:molecule-co2",
    SENSOR_FREQUENCY: "mdi:current-ac",
    SENSOR_MOISTURE: "mdi:cup-water",
    SENSOR_PB0_3: "mdi:flask",
    SENSOR_PB0_5: "mdi:flask",
    SENSOR_PB10: "mdi:flask",
    SENSOR_PB1: "mdi:flask",
    SENSOR_PB2_5: "mdi:flask",
    SENSOR_PB5: "mdi:flask",
    SENSOR_PM10: "mdi:air-filter",
    SENSOR_PM1: "mdi:air-filter",
    SENSOR_PM2_5: "mdi:air-filter",
    SENSOR_POWERFACTOR: "mdi:alpha-f-circle-outline",
    SENSOR_PROXIMITY: "mdi:ruler",
    SENSOR_TOTAL_START_TIME: "mdi:progress-clock",
    SENSOR_TVOC: "mdi:air-filter",
    SENSOR_VOLTAGE: "mdi:alpha-v-circle-outline",
    SENSOR_WEIGHT: "mdi:scale",
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

    async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(sensor.DOMAIN, TASMOTA_DOMAIN),
        async_discover_sensor,
    )


class TasmotaSensor(TasmotaAvailability, TasmotaDiscoveryUpdate, Entity):
    """Representation of a Tasmota sensor."""

    def __init__(self, **kwds):
        """Initialize the Tasmota sensor."""
        self._state = False

        super().__init__(
            discovery_update=self.discovery_update,
            **kwds,
        )

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return SENSOR_DEVICE_CLASS_MAP.get(self._tasmota_entity.quantity)

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_ICON_MAP.get(self._tasmota_entity.quantity)

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._tasmota_entity.unit
