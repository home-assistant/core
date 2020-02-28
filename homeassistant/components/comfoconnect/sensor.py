"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
import logging

from pycomfoconnect import (
    SENSOR_BYPASS_STATE,
    SENSOR_DAYS_TO_REPLACE_FILTER,
    SENSOR_FAN_EXHAUST_DUTY,
    SENSOR_FAN_EXHAUST_FLOW,
    SENSOR_FAN_EXHAUST_SPEED,
    SENSOR_FAN_SUPPLY_DUTY,
    SENSOR_FAN_SUPPLY_FLOW,
    SENSOR_FAN_SUPPLY_SPEED,
    SENSOR_HUMIDITY_EXHAUST,
    SENSOR_HUMIDITY_EXTRACT,
    SENSOR_HUMIDITY_OUTDOOR,
    SENSOR_HUMIDITY_SUPPLY,
    SENSOR_POWER_CURRENT,
    SENSOR_TEMPERATURE_EXHAUST,
    SENSOR_TEMPERATURE_EXTRACT,
    SENSOR_TEMPERATURE_OUTDOOR,
    SENSOR_TEMPERATURE_SUPPLY,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_RESOURCES,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_DAYS,
    TIME_HOURS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

ATTR_AIR_FLOW_EXHAUST = "air_flow_exhaust"
ATTR_AIR_FLOW_SUPPLY = "air_flow_supply"
ATTR_BYPASS_STATE = "bypass_state"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_DAYS_TO_REPLACE_FILTER = "days_to_replace_filter"
ATTR_EXHAUST_FAN_DUTY = "exhaust_fan_duty"
ATTR_EXHAUST_FAN_SPEED = "exhaust_fan_speed"
ATTR_EXHAUST_HUMIDITY = "exhaust_humidity"
ATTR_EXHAUST_TEMPERATURE = "exhaust_temperature"
ATTR_OUTSIDE_HUMIDITY = "outside_humidity"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_POWER_CURRENT = "power_usage"
ATTR_SUPPLY_FAN_DUTY = "supply_fan_duty"
ATTR_SUPPLY_FAN_SPEED = "supply_fan_speed"
ATTR_SUPPLY_HUMIDITY = "supply_humidity"
ATTR_SUPPLY_TEMPERATURE = "supply_temperature"

_LOGGER = logging.getLogger(__name__)

ATTR_ICON = "icon"
ATTR_ID = "id"
ATTR_LABEL = "label"
ATTR_MULTIPLIER = "multiplier"
ATTR_UNIT = "unit"

SENSOR_TYPES = {
    ATTR_CURRENT_TEMPERATURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_LABEL: "Inside Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ID: SENSOR_TEMPERATURE_EXTRACT,
        ATTR_MULTIPLIER: 0.1,
    },
    ATTR_CURRENT_HUMIDITY: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_LABEL: "Inside Humidity",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:water-percent",
        ATTR_ID: SENSOR_HUMIDITY_EXTRACT,
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_LABEL: "Outside Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ID: SENSOR_TEMPERATURE_OUTDOOR,
        ATTR_MULTIPLIER: 0.1,
    },
    ATTR_OUTSIDE_HUMIDITY: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_LABEL: "Outside Humidity",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:water-percent",
        ATTR_ID: SENSOR_HUMIDITY_OUTDOOR,
    },
    ATTR_SUPPLY_TEMPERATURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_LABEL: "Supply Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ID: SENSOR_TEMPERATURE_SUPPLY,
        ATTR_MULTIPLIER: 0.1,
    },
    ATTR_SUPPLY_HUMIDITY: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_LABEL: "Supply Humidity",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:water-percent",
        ATTR_ID: SENSOR_HUMIDITY_SUPPLY,
    },
    ATTR_SUPPLY_FAN_SPEED: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Supply Fan Speed",
        ATTR_UNIT: "rpm",
        ATTR_ICON: "mdi:fan",
        ATTR_ID: SENSOR_FAN_SUPPLY_SPEED,
    },
    ATTR_SUPPLY_FAN_DUTY: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Supply Fan Duty",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:fan",
        ATTR_ID: SENSOR_FAN_SUPPLY_DUTY,
    },
    ATTR_EXHAUST_FAN_SPEED: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Exhaust Fan Speed",
        ATTR_UNIT: "rpm",
        ATTR_ICON: "mdi:fan",
        ATTR_ID: SENSOR_FAN_EXHAUST_SPEED,
    },
    ATTR_EXHAUST_FAN_DUTY: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Exhaust Fan Duty",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:fan",
        ATTR_ID: SENSOR_FAN_EXHAUST_DUTY,
    },
    ATTR_EXHAUST_TEMPERATURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_LABEL: "Exhaust Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ID: SENSOR_TEMPERATURE_EXHAUST,
        ATTR_MULTIPLIER: 0.1,
    },
    ATTR_EXHAUST_HUMIDITY: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_LABEL: "Exhaust Humidity",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:water-percent",
        ATTR_ID: SENSOR_HUMIDITY_EXHAUST,
    },
    ATTR_AIR_FLOW_SUPPLY: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Supply airflow",
        ATTR_UNIT: f"m³/{TIME_HOURS}",
        ATTR_ICON: "mdi:fan",
        ATTR_ID: SENSOR_FAN_SUPPLY_FLOW,
    },
    ATTR_AIR_FLOW_EXHAUST: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Exhaust airflow",
        ATTR_UNIT: f"m³/{TIME_HOURS}",
        ATTR_ICON: "mdi:fan",
        ATTR_ID: SENSOR_FAN_EXHAUST_FLOW,
    },
    ATTR_BYPASS_STATE: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Bypass State",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_ICON: "mdi:camera-iris",
        ATTR_ID: SENSOR_BYPASS_STATE,
    },
    ATTR_DAYS_TO_REPLACE_FILTER: {
        ATTR_DEVICE_CLASS: None,
        ATTR_LABEL: "Days to replace filter",
        ATTR_UNIT: TIME_DAYS,
        ATTR_ICON: "mdi:calendar",
        ATTR_ID: SENSOR_DAYS_TO_REPLACE_FILTER,
    },
    ATTR_POWER_CURRENT: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_LABEL: "Power usage",
        ATTR_UNIT: POWER_WATT,
        ATTR_ICON: "mdi:flash",
        ATTR_ID: SENSOR_POWER_CURRENT,
    },
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ComfoConnect fan platform."""
    ccb = hass.data[DOMAIN]

    sensors = []
    for resource in config[CONF_RESOURCES]:
        sensors.append(
            ComfoConnectSensor(
                name=f"{ccb.name} {SENSOR_TYPES[resource][ATTR_LABEL]}",
                ccb=ccb,
                sensor_type=resource,
            )
        )

    add_entities(sensors, True)


class ComfoConnectSensor(Entity):
    """Representation of a ComfoConnect sensor."""

    def __init__(self, name, ccb: ComfoConnectBridge, sensor_type) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self._sensor_type = sensor_type
        self._sensor_id = SENSOR_TYPES[self._sensor_type][ATTR_ID]
        self._name = name

    async def async_added_to_hass(self):
        """Register for sensor updates."""
        _LOGGER.debug(
            "Registering for sensor %s (%d)", self._sensor_type, self._sensor_id
        )
        async_dispatcher_connect(
            self.hass,
            SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(self._sensor_id),
            self._handle_update,
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, self._sensor_id
        )

    def _handle_update(self, value):
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for sensor %s (%d): %s",
            self._sensor_type,
            self._sensor_id,
            value,
        )
        self._ccb.data[self._sensor_id] = round(
            value * SENSOR_TYPES[self._sensor_type].get(ATTR_MULTIPLIER, 1), 2
        )
        self.schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the entity."""
        try:
            return self._ccb.data[self._sensor_id]
        except KeyError:
            return None

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._ccb.unique_id}-{self._sensor_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return SENSOR_TYPES[self._sensor_type][ATTR_ICON]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return SENSOR_TYPES[self._sensor_type][ATTR_UNIT]

    @property
    def device_class(self):
        """Return the device_class."""
        return SENSOR_TYPES[self._sensor_type][ATTR_DEVICE_CLASS]
