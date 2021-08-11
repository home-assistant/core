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


SENSOR_TYPES = (
    ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Inside temperature",
        unit_of_measurement=TEMP_CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_EXTRACT,
        multiplier=0.1,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Inside humidity",
        unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_EXTRACT,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_CURRENT_RMOT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current RMOT",
        unit_of_measurement=TEMP_CELSIUS,
        sensor_id=SENSOR_CURRENT_RMOT,
        multiplier=0.1,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_OUTSIDE_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Outside temperature",
        unit_of_measurement=TEMP_CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_OUTDOOR,
        multiplier=0.1,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_OUTSIDE_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Outside humidity",
        unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_OUTDOOR,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Supply temperature",
        unit_of_measurement=TEMP_CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_SUPPLY,
        multiplier=0.1,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Supply humidity",
        unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_SUPPLY,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_FAN_SPEED,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Supply fan speed",
        unit_of_measurement="rpm",
        icon="mdi:fan-plus",
        sensor_id=SENSOR_FAN_SUPPLY_SPEED,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_SUPPLY_FAN_DUTY,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Supply fan duty",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:fan-plus",
        sensor_id=SENSOR_FAN_SUPPLY_DUTY,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_FAN_SPEED,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Exhaust fan speed",
        unit_of_measurement="rpm",
        icon="mdi:fan-minus",
        sensor_id=SENSOR_FAN_EXHAUST_SPEED,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_FAN_DUTY,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Exhaust fan duty",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:fan-minus",
        sensor_id=SENSOR_FAN_EXHAUST_DUTY,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Exhaust temperature",
        unit_of_measurement=TEMP_CELSIUS,
        sensor_id=SENSOR_TEMPERATURE_EXHAUST,
        multiplier=0.1,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_EXHAUST_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Exhaust humidity",
        unit_of_measurement=PERCENTAGE,
        sensor_id=SENSOR_HUMIDITY_EXHAUST,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_AIR_FLOW_SUPPLY,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Supply airflow",
        unit_of_measurement=VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        icon="mdi:fan-plus",
        sensor_id=SENSOR_FAN_SUPPLY_FLOW,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_AIR_FLOW_EXHAUST,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Exhaust airflow",
        unit_of_measurement=VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        icon="mdi:fan-minus",
        sensor_id=SENSOR_FAN_EXHAUST_FLOW,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_BYPASS_STATE,
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Bypass state",
        unit_of_measurement=PERCENTAGE,
        icon="mdi:camera-iris",
        sensor_id=SENSOR_BYPASS_STATE,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_DAYS_TO_REPLACE_FILTER,
        device_class=None,
        name="Days to replace filter",
        unit_of_measurement=TIME_DAYS,
        icon="mdi:calendar",
        sensor_id=SENSOR_DAYS_TO_REPLACE_FILTER,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_POWER_CURRENT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Power usage",
        unit_of_measurement=POWER_WATT,
        sensor_id=SENSOR_POWER_CURRENT,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_POWER_TOTAL,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Energy total",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        sensor_id=SENSOR_POWER_TOTAL,
        last_reset=dt.utc_from_timestamp(0),
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_PREHEATER_POWER_CURRENT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Preheater power usage",
        unit_of_measurement=POWER_WATT,
        sensor_id=SENSOR_PREHEATER_POWER_CURRENT,
    ),
    ComfoconnectSensorEntityDescription(
        key=ATTR_PREHEATER_POWER_TOTAL,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Preheater energy total",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        sensor_id=SENSOR_PREHEATER_POWER_TOTAL,
        last_reset=dt.utc_from_timestamp(0),
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In([desc.key for desc in SENSOR_TYPES])]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ComfoConnect sensor platform."""
    ccb = hass.data[DOMAIN]

    sensors = [
        ComfoConnectSensor(ccb=ccb, description=description)
        for description in SENSOR_TYPES
        if description.key in config[CONF_RESOURCES]
    ]

    add_entities(sensors, True)


class ComfoConnectSensor(SensorEntity):
    """Representation of a ComfoConnect sensor."""

    _attr_should_poll = False
    entity_description: ComfoconnectSensorEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        description: ComfoconnectSensorEntityDescription,
    ) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self.entity_description = description
        self._attr_name = f"{ccb.name} {self.entity_description.name}"
        self._attr_unique_id = f"{self._ccb.unique_id}-{self.entity_description.key}"

    async def async_added_to_hass(self):
        """Register for sensor updates."""
        _LOGGER.debug(
            "Registering for sensor %s (%d)",
            self.entity_description.key,
            self.entity_description.sensor_id,
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(
                    self.entity_description.sensor_id
                ),
                self._handle_update,
            )
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, self.entity_description.sensor_id
        )

    def _handle_update(self, value):
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for sensor %s (%d): %s",
            self.entity_description.key,
            self.entity_description.sensor_id,
            value,
        )
        self._ccb.data[self.entity_description.sensor_id] = round(
            value * self.entity_description.multiplier, 2
        )
        self.schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the entity."""
        try:
            return self._ccb.data[self.entity_description.sensor_id]
        except KeyError:
            return None
