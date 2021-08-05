"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
from dataclasses import dataclass
import logging

from pycomfoconnect import (
    SENSOR_BYPASS_STATE,
    SENSOR_CURRENT_RMOT,
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
    SENSOR_POWER_TOTAL,
    SENSOR_PREHEATER_POWER_CURRENT,
    SENSOR_PREHEATER_POWER_TOTAL,
    SENSOR_TEMPERATURE_EXHAUST,
    SENSOR_TEMPERATURE_EXTRACT,
    SENSOR_TEMPERATURE_OUTDOOR,
    SENSOR_TEMPERATURE_SUPPLY,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_RESOURCES,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_DAYS,
    VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

ATTR_AIR_FLOW_EXHAUST = "air_flow_exhaust"
ATTR_AIR_FLOW_SUPPLY = "air_flow_supply"
ATTR_BYPASS_STATE = "bypass_state"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_RMOT = "current_rmot"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_DAYS_TO_REPLACE_FILTER = "days_to_replace_filter"
ATTR_EXHAUST_FAN_DUTY = "exhaust_fan_duty"
ATTR_EXHAUST_FAN_SPEED = "exhaust_fan_speed"
ATTR_EXHAUST_HUMIDITY = "exhaust_humidity"
ATTR_EXHAUST_TEMPERATURE = "exhaust_temperature"
ATTR_OUTSIDE_HUMIDITY = "outside_humidity"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_POWER_CURRENT = "power_usage"
ATTR_POWER_TOTAL = "power_total"
ATTR_PREHEATER_POWER_CURRENT = "preheater_power_usage"
ATTR_PREHEATER_POWER_TOTAL = "preheater_power_total"
ATTR_SUPPLY_FAN_DUTY = "supply_fan_duty"
ATTR_SUPPLY_FAN_SPEED = "supply_fan_speed"
ATTR_SUPPLY_HUMIDITY = "supply_humidity"
ATTR_SUPPLY_TEMPERATURE = "supply_temperature"

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComfoconnectRequiredKeysMixin:
    """Mixin for required keys."""

    sensor_id: int


@dataclass
class ComfoconnectSensorEntityDescription(
    SensorEntityDescription, ComfoconnectRequiredKeysMixin
):
    """Describes Comfoconnect sensor entity."""

    multiplier: float = 1


SENSOR_TYPES = {
    ATTR_CURRENT_TEMPERATURE: ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name="Inside Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        sensor_id=SENSOR_TEMPERATURE_EXTRACT,
        multiplier=0.1,
    ),
    ATTR_CURRENT_HUMIDITY: ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        name="Inside Humidity",
        unit_of_measurement=PERCENTAGE,
        icon=None,
        sensor_id=SENSOR_HUMIDITY_EXTRACT,
    ),
    ATTR_CURRENT_RMOT: ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_RMOT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name="Current RMOT",
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        sensor_id=SENSOR_CURRENT_RMOT,
        multiplier=0.1,
    ),
    ATTR_OUTSIDE_TEMPERATURE: ComfoconnectSensorEntityDescription(
        key=ATTR_OUTSIDE_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name="Outside Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        sensor_id=SENSOR_TEMPERATURE_OUTDOOR,
        multiplier=0.1,
    ),
    ATTR_OUTSIDE_HUMIDITY: ComfoconnectSensorEntityDescription(
        key=ATTR_OUTSIDE_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        name="Outside Humidity",
        unit_of_measurement=PERCENTAGE,
        icon=None,
        sensor_id=SENSOR_HUMIDITY_OUTDOOR,
    ),
    ATTR_SUPPLY_TEMPERATURE: ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name="Supply Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        sensor_id=SENSOR_TEMPERATURE_SUPPLY,
        multiplier=0.1,
    ),
    ATTR_SUPPLY_HUMIDITY: ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        name="Supply Humidity",
        unit_of_measurement=PERCENTAGE,
        icon=None,
        sensor_id=SENSOR_HUMIDITY_SUPPLY,
    ),
    ATTR_SUPPLY_FAN_SPEED: ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_FAN_SPEED,
        device_class=None,
        name="Supply Fan Speed",
        unit_of_measurement="rpm",
        icon="mdi:fan",
        sensor_id=SENSOR_FAN_SUPPLY_SPEED,
    ),
    ATTR_SUPPLY_FAN_DUTY: ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_FAN_DUTY,
        device_class=None,
        name="Supply Fan Duty",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:fan",
        sensor_id=SENSOR_FAN_SUPPLY_DUTY,
    ),
    ATTR_EXHAUST_FAN_SPEED: ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_FAN_SPEED,
        device_class=None,
        name="Exhaust Fan Speed",
        unit_of_measurement="rpm",
        icon="mdi:fan",
        sensor_id=SENSOR_FAN_EXHAUST_SPEED,
    ),
    ATTR_EXHAUST_FAN_DUTY: ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_FAN_DUTY,
        device_class=None,
        name="Exhaust Fan Duty",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:fan",
        sensor_id=SENSOR_FAN_EXHAUST_DUTY,
    ),
    ATTR_EXHAUST_TEMPERATURE: ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name="Exhaust Temperature",
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        sensor_id=SENSOR_TEMPERATURE_EXHAUST,
        multiplier=0.1,
    ),
    ATTR_EXHAUST_HUMIDITY: ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        name="Exhaust Humidity",
        unit_of_measurement=PERCENTAGE,
        icon=None,
        sensor_id=SENSOR_HUMIDITY_EXHAUST,
    ),
    ATTR_AIR_FLOW_SUPPLY: ComfoconnectSensorEntityDescription(
        key=ATTR_AIR_FLOW_SUPPLY,
        device_class=None,
        name="Supply airflow",
        unit_of_measurement=VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        icon="mdi:fan",
        sensor_id=SENSOR_FAN_SUPPLY_FLOW,
    ),
    ATTR_AIR_FLOW_EXHAUST: ComfoconnectSensorEntityDescription(
        key=ATTR_AIR_FLOW_EXHAUST,
        device_class=None,
        name="Exhaust airflow",
        unit_of_measurement=VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        icon="mdi:fan",
        sensor_id=SENSOR_FAN_EXHAUST_FLOW,
    ),
    ATTR_BYPASS_STATE: ComfoconnectSensorEntityDescription(
        key=ATTR_BYPASS_STATE,
        device_class=None,
        name="Bypass State",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:camera-iris",
        sensor_id=SENSOR_BYPASS_STATE,
    ),
    ATTR_DAYS_TO_REPLACE_FILTER: ComfoconnectSensorEntityDescription(
        key=ATTR_DAYS_TO_REPLACE_FILTER,
        device_class=None,
        name="Days to replace filter",
        unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar",
        sensor_id=SENSOR_DAYS_TO_REPLACE_FILTER,
    ),
    ATTR_POWER_CURRENT: ComfoconnectSensorEntityDescription(
        key=ATTR_POWER_CURRENT,
        device_class=DEVICE_CLASS_POWER,
        name="Power usage",
        unit_of_measurement=POWER_WATT,
        icon=None,
        sensor_id=SENSOR_POWER_CURRENT,
    ),
    ATTR_POWER_TOTAL: ComfoconnectSensorEntityDescription(
        key=ATTR_POWER_TOTAL,
        device_class=DEVICE_CLASS_ENERGY,
        name="Power total",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon=None,
        sensor_id=SENSOR_POWER_TOTAL,
        last_reset=dt.utc_from_timestamp(0),
    ),
    ATTR_PREHEATER_POWER_CURRENT: ComfoconnectSensorEntityDescription(
        key=ATTR_PREHEATER_POWER_CURRENT,
        device_class=DEVICE_CLASS_POWER,
        name="Preheater power usage",
        unit_of_measurement=POWER_WATT,
        icon=None,
        sensor_id=SENSOR_PREHEATER_POWER_CURRENT,
    ),
    ATTR_PREHEATER_POWER_TOTAL: ComfoconnectSensorEntityDescription(
        key=ATTR_PREHEATER_POWER_TOTAL,
        device_class=DEVICE_CLASS_ENERGY,
        name="Preheater power total",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon=None,
        sensor_id=SENSOR_PREHEATER_POWER_TOTAL,
        last_reset=dt.utc_from_timestamp(0),
    ),
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
                name=f"{ccb.name} {SENSOR_TYPES[resource].name}",
                ccb=ccb,
                sensor_type=resource,
            )
        )

    add_entities(sensors, True)


class ComfoConnectSensor(SensorEntity):
    """Representation of a ComfoConnect sensor."""

    def __init__(self, name, ccb: ComfoConnectBridge, sensor_type) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self._sensor_type = sensor_type
        self._sensor_id = SENSOR_TYPES[self._sensor_type].sensor_id
        self._name = name

    async def async_added_to_hass(self):
        """Register for sensor updates."""
        _LOGGER.debug(
            "Registering for sensor %s (%d)", self._sensor_type, self._sensor_id
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(self._sensor_id),
                self._handle_update,
            )
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
            value * SENSOR_TYPES[self._sensor_type].multiplier, 2
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
        return SENSOR_TYPES[self._sensor_type].icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return SENSOR_TYPES[self._sensor_type].unit_of_measurement

    @property
    def device_class(self):
        """Return the device_class."""
        return SENSOR_TYPES[self._sensor_type].device_class

    @property
    def state_class(self):
        """Return the state_class."""
        return STATE_CLASS_MEASUREMENT

    @property
    def last_reset(self):
        """Return the last_reset."""
        return SENSOR_TYPES[self._sensor_type].last_reset
