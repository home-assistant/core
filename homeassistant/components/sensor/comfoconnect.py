"""
Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.comfoconnect/
"""
import logging

from homeassistant.components.comfoconnect import (
    DOMAIN, ComfoConnectBridge, ATTR_CURRENT_TEMPERATURE,
    ATTR_CURRENT_HUMIDITY, ATTR_OUTSIDE_TEMPERATURE,
    ATTR_OUTSIDE_HUMIDITY, ATTR_AIR_FLOW_SUPPLY,
    ATTR_AIR_FLOW_EXHAUST, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED)
from homeassistant.const import (
    CONF_RESOURCES, TEMP_CELSIUS, STATE_UNKNOWN)
from homeassistant.helpers.dispatcher import dispatcher_connect
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['comfoconnect']

SENSOR_TYPES = {}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ComfoConnect fan platform."""
    from pycomfoconnect import (
        SENSOR_TEMPERATURE_EXTRACT, SENSOR_HUMIDITY_EXTRACT,
        SENSOR_TEMPERATURE_OUTDOOR, SENSOR_HUMIDITY_OUTDOOR,
        SENSOR_FAN_SUPPLY_FLOW, SENSOR_FAN_EXHAUST_FLOW)

    global SENSOR_TYPES
    SENSOR_TYPES = {
        ATTR_CURRENT_TEMPERATURE: [
            'Inside Temperature',
            TEMP_CELSIUS,
            'mdi:thermometer',
            SENSOR_TEMPERATURE_EXTRACT
        ],
        ATTR_CURRENT_HUMIDITY: [
            'Inside Humidity',
            '%',
            'mdi:water-percent',
            SENSOR_HUMIDITY_EXTRACT
        ],
        ATTR_OUTSIDE_TEMPERATURE: [
            'Outside Temperature',
            TEMP_CELSIUS,
            'mdi:thermometer',
            SENSOR_TEMPERATURE_OUTDOOR
        ],
        ATTR_OUTSIDE_HUMIDITY: [
            'Outside Humidity',
            '%',
            'mdi:water-percent',
            SENSOR_HUMIDITY_OUTDOOR
        ],
        ATTR_AIR_FLOW_SUPPLY: [
            'Supply airflow',
            'm³/h',
            'mdi:air-conditioner',
            SENSOR_FAN_SUPPLY_FLOW
        ],
        ATTR_AIR_FLOW_EXHAUST: [
            'Exhaust airflow',
            'm³/h',
            'mdi:air-conditioner',
            SENSOR_FAN_EXHAUST_FLOW
        ],
    }

    ccb = hass.data[DOMAIN]

    sensors = []
    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        if sensor_type not in SENSOR_TYPES:
            _LOGGER.warning("Sensor type: %s is not a valid sensor.",
                            sensor_type)
            continue

        sensors.append(
            ComfoConnectSensor(
                hass,
                name="%s %s" % (ccb.name, SENSOR_TYPES[sensor_type][0]),
                ccb=ccb,
                sensor_type=sensor_type
            )
        )

    add_devices(sensors, True)


class ComfoConnectSensor(Entity):
    """Representation of a ComfoConnect sensor."""

    def __init__(self, hass, name, ccb: ComfoConnectBridge,
                 sensor_type) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self._sensor_type = sensor_type
        self._sensor_id = SENSOR_TYPES[self._sensor_type][3]
        self._name = name

        # Register the requested sensor
        self._ccb.comfoconnect.register_sensor(self._sensor_id)

        def _handle_update(var):
            if var == self._sensor_id:
                _LOGGER.debug('Dispatcher update for %s.', var)
                self.schedule_update_ha_state()

        # Register for dispatcher updates
        dispatcher_connect(
            hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, _handle_update)

    @property
    def state(self):
        """Return the state of the entity."""
        try:
            return self._ccb.data[self._sensor_id]
        except KeyError:
            return STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return SENSOR_TYPES[self._sensor_type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._sensor_type][1]
