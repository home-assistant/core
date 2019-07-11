"""Platform to control a SystemAIR VTR ventilation unit."""
import logging

from homeassistant.const import CONF_RESOURCES, TEMP_CELSIUS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import (
    ATTR_ALARM_BYPASS_DAMPER, ATTR_ALARM_BYPASS_DAMPER_2,
    ATTR_ALARM_CHANGE_FILTER, ATTR_ALARM_CO2, ATTR_ALARM_DEFROST,
    ATTR_ALARM_EFFICIENCY_TEMP_SENSOR, ATTR_ALARM_ELECTRICAL_HEATER,
    ATTR_ALARM_EXTERNAL_STOP, ATTR_ALARM_EXTRA_CONTROLLER,
    ATTR_ALARM_EXTRACT_FLOW_PRESSURE, ATTR_ALARM_EXTRACT_RPM,
    ATTR_ALARM_EXTRACT_TEMP_SENSOR, ATTR_ALARM_FROST_PROTECTION,
    ATTR_ALARM_FROST_PROTECTION_SENSOR, ATTR_ALARM_INCORRECT_MANUAL_MODE,
    ATTR_ALARM_INDOOR_TEMP_SENSOR, ATTR_ALARM_MANUAL_STOP,
    ATTR_ALARM_OUTDOOR_TEMP_SENSOR, ATTR_ALARM_PDM_RH, ATTR_ALARM_PDM_TEMP,
    ATTR_ALARM_PREHEATER_TEMP_SENSOR, ATTR_ALARM_REHEATER_OVERHEAT,
    ATTR_ALARM_REHEATER_TEMP_SENSOR, ATTR_ALARM_RH,
    ATTR_ALARM_ROTARY_EXCHANGER, ATTR_ALARM_SUPPLY_FLOW_PRESSURE,
    ATTR_ALARM_SUPPLY_RPM, ATTR_ALARM_SUPPLY_TEMP_SENSOR,
    ATTR_CURRENT_FAN_MODE, ATTR_CURRENT_HUMIDITY, ATTR_CURRENT_OPERATION,
    ATTR_EXTRACT_TEMPERATURE, ATTR_FAN_SPEED_EXTRACT, ATTR_FAN_SPEED_SUPPLY,
    ATTR_FILTER_TIME, ATTR_FUNCTION_COOKER_HOOD, ATTR_FUNCTION_COOLING,
    ATTR_FUNCTION_COOLING_RECOVERY, ATTR_FUNCTION_DEFROSTING,
    ATTR_FUNCTION_FREE_COOLING, ATTR_FUNCTION_HEAT_RECOVERY,
    ATTR_FUNCTION_HEATER_COOLDOWN, ATTR_FUNCTION_HEATING,
    ATTR_FUNCTION_MOISTURE_TRANSFER, ATTR_FUNCTION_SECONDARY_AIR,
    ATTR_FUNCTION_SERVICE_USER_LOCK, ATTR_FUNCTION_VACUUM_CLEANER,
    ATTR_OUTSIDE_TEMPERATURE, ATTR_SUPPLY_TEMPERATURE, ATTR_TARGET_TEMPERATURE,
    ATTR_USER_LOCK, DOMAIN, SIGNAL_SYSTEMAIR_UPDATE_RECEIVED, SystemAIRBridge)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):

    """Set up the Systemair fan platform."""
    from systemair.savecair.const import (
        SENSOR_TEMPERATURE_EXTRACT,
        SENSOR_CURRENT_HUMIDITY,
        SENSOR_TEMPERATURE_OUTDOOR,
        SENSOR_FAN_SPEED_SUPPLY,
        SENSOR_FAN_SPEED_EXTRACT,
        SENSOR_TEMPERATURE_SUPPLY,
        SENSOR_FILTER_TIME,
        SENSOR_CURRENT_OPERATION,
        SENSOR_CURRENT_FAN_MODE,
        SENSOR_USER_LOCK,
        SENSOR_FUNCTION_COOLING,
        SENSOR_FUNCTION_FREE_COOLING,
        SENSOR_FUNCTION_HEATING,
        SENSOR_FUNCTION_DEFROSTING,
        SENSOR_FUNCTION_HEAT_RECOVERY,
        SENSOR_FUNCTION_COOLING_RECOVERY,
        SENSOR_FUNCTION_MOISTURE_TRANSFER,
        SENSOR_FUNCTION_SECONDARY_AIR,
        SENSOR_FUNCTION_COOKER_HOOD,
        SENSOR_FUNCTION_HEATER_COOLDOWN,
        SENSOR_FUNCTION_SERVICE_USER_LOCK,
        SENSOR_ALARM_INCORRECT_MANUAL_MODE,
        SENSOR_ALARM_RH,
        SENSOR_ALARM_CO2,
        SENSOR_ALARM_REHEATER_OVERHEAT,
        SENSOR_ALARM_MANUAL_STOP,
        SENSOR_ALARM_EXTERNAL_STOP,
        SENSOR_ALARM_EXTRA_CONTROLLER,
        SENSOR_ALARM_CHANGE_FILTER,
        SENSOR_ALARM_PDM_TEMP,
        SENSOR_ALARM_EFFICIENCY_TEMP_SENSOR,
        SENSOR_ALARM_PREHEATER_TEMP_SENSOR,
        SENSOR_ALARM_EXTRACT_TEMP_SENSOR,
        SENSOR_ALARM_INDOOR_TEMP_SENSOR,
        SENSOR_ALARM_SUPPLY_TEMP_SENSOR,
        SENSOR_ALARM_REHEATER_TEMP_SENSOR,
        SENSOR_ALARM_OUTDOOR_TEMP_SENSOR,
        SENSOR_ALARM_BYPASS_DAMPER_2,
        SENSOR_ALARM_ROTARY_EXCHANGER,
        SENSOR_ALARM_BYPASS_DAMPER,
        SENSOR_ALARM_ELECTRICAL_HEATER,
        SENSOR_ALARM_EXTRACT_FLOW_PRESSURE,
        SENSOR_ALARM_SUPPLY_FLOW_PRESSURE,
        SENSOR_ALARM_EXTRACT_RPM,
        SENSOR_ALARM_SUPPLY_RPM,
        SENSOR_ALARM_DEFROST,
        SENSOR_ALARM_FROST_PROTECTION_SENSOR,
        SENSOR_ALARM_FROST_PROTECTION,
        SENSOR_ALARM_PDM_RH,
        SENSOR_FUNCTION_VACUUM_CLEANER,
        SENSOR_TARGET_TEMPERATURE
    )

    global SENSOR_TYPES
    SENSOR_TYPES = {
        ATTR_FAN_SPEED_EXTRACT: [
            'Extract Fan-Speed',
            'RPM',
            'mdi:air-conditioner',
            SENSOR_FAN_SPEED_EXTRACT

        ],
        ATTR_FAN_SPEED_SUPPLY: [
            'Supply Fan-Speed',
            'RPM',
            'mdi:air-conditioner',
            SENSOR_FAN_SPEED_SUPPLY
        ],

        ATTR_OUTSIDE_TEMPERATURE: [
            'Outside Temperature',
            TEMP_CELSIUS,
            'mdi:thermometer',
            SENSOR_TEMPERATURE_OUTDOOR
        ],
        ATTR_SUPPLY_TEMPERATURE: [
            'Supply Temperature',
            TEMP_CELSIUS,
            'mdi:thermometer',
            SENSOR_TEMPERATURE_SUPPLY
        ],
        ATTR_EXTRACT_TEMPERATURE: [
            'Extract Temperature',
            TEMP_CELSIUS,
            'mdi:thermometer',
            SENSOR_TEMPERATURE_EXTRACT
        ],

        ATTR_CURRENT_HUMIDITY: [
            'Inside Humidity',
            '%',
            'mdi:water-percent',
            SENSOR_CURRENT_HUMIDITY
        ],

        ATTR_FILTER_TIME: [
            'Filter Replacement',
            'days',
            'mdi:alarm',
            SENSOR_FILTER_TIME
        ],

        ATTR_CURRENT_FAN_MODE: [
            'Fan Mode',
            '',
            'mdi:fan',
            SENSOR_CURRENT_FAN_MODE
        ],

        ATTR_CURRENT_OPERATION: [
            'Operation Mode',
            '',
            'mdi:water-percent',
            SENSOR_CURRENT_OPERATION
        ],

        ATTR_USER_LOCK: [
            'User Lock',
            '',
            'mdi:account-alert',
            SENSOR_USER_LOCK
        ],

        ATTR_FUNCTION_COOLING: [
            'Cooling',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_COOLING
        ],

        ATTR_FUNCTION_VACUUM_CLEANER: [
            'Vacuum Cleaner',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_VACUUM_CLEANER
        ],
        ATTR_FUNCTION_FREE_COOLING: [
            'Free Cooling',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_FREE_COOLING
        ],
        ATTR_FUNCTION_HEATING: [
            'Heating',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_HEATING
        ],
        ATTR_FUNCTION_DEFROSTING: [
            'Defrosting',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_DEFROSTING
        ],
        ATTR_FUNCTION_HEAT_RECOVERY: [
            'Heat Recovery',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_HEAT_RECOVERY
        ],
        ATTR_FUNCTION_COOLING_RECOVERY: [
            'Cooling Recovery',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_COOLING_RECOVERY
        ],
        ATTR_FUNCTION_MOISTURE_TRANSFER: [
            'Moisture Transfer',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_MOISTURE_TRANSFER
        ],
        ATTR_FUNCTION_SECONDARY_AIR: [
            'Secondary Air',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_SECONDARY_AIR
        ],
        ATTR_FUNCTION_COOKER_HOOD: [
            'Cooker Hood',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_COOKER_HOOD
        ],
        ATTR_FUNCTION_HEATER_COOLDOWN: [
            'Heater Cooldown',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_HEATER_COOLDOWN
        ],
        ATTR_FUNCTION_SERVICE_USER_LOCK: [
            'Service User Lock',
            '',
            'mdi:bell',
            SENSOR_FUNCTION_SERVICE_USER_LOCK
        ],


        ATTR_ALARM_FROST_PROTECTION: [
            'Alarm Frost Protection',
            '',
            'mdi:alert',
            SENSOR_ALARM_FROST_PROTECTION
        ],
        ATTR_ALARM_FROST_PROTECTION_SENSOR: [
            'Alarm Frost Protection Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_FROST_PROTECTION_SENSOR
        ],
        ATTR_ALARM_DEFROST: [
            'Alarm Defrost',
            '',
            'mdi:alert',
            SENSOR_ALARM_DEFROST
        ],
        ATTR_ALARM_SUPPLY_RPM: [
            'Alarm Supply RPM',
            '',
            'mdi:alert',
            SENSOR_ALARM_SUPPLY_RPM
        ],
        ATTR_ALARM_EXTRACT_RPM: [
            'Alarm Extract RPM',
            '',
            'mdi:alert',
            SENSOR_ALARM_EXTRACT_RPM
        ],
        ATTR_ALARM_SUPPLY_FLOW_PRESSURE: [
            'Alarm Supply Flow & Pressure',
            '',
            'mdi:alert',
            SENSOR_ALARM_SUPPLY_FLOW_PRESSURE
        ],
        ATTR_ALARM_EXTRACT_FLOW_PRESSURE: [
            'Alarm Extract Flow & Pressure',
            '',
            'mdi:alert',
            SENSOR_ALARM_EXTRACT_FLOW_PRESSURE
        ],
        ATTR_ALARM_ELECTRICAL_HEATER: [
            'Alarm Electrical Heater',
            '',
            'mdi:alert',
            SENSOR_ALARM_ELECTRICAL_HEATER
        ],
        ATTR_ALARM_BYPASS_DAMPER: [
            'Alarm Bypass Damper',
            '',
            'mdi:alert',
            SENSOR_ALARM_BYPASS_DAMPER
        ],
        ATTR_ALARM_ROTARY_EXCHANGER: [
            'Alarm Rotary Exchanger',
            '',
            'mdi:alert',
            SENSOR_ALARM_ROTARY_EXCHANGER
        ],
        ATTR_ALARM_BYPASS_DAMPER_2: [
            'Alarm Bypass Damper Secondary',
            '',
            'mdi:alert',
            SENSOR_ALARM_BYPASS_DAMPER_2
        ],
        ATTR_ALARM_OUTDOOR_TEMP_SENSOR: [
            'Alarm Outdoor Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_OUTDOOR_TEMP_SENSOR
        ],
        ATTR_ALARM_REHEATER_TEMP_SENSOR: [
            'Alarm Reheater Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_REHEATER_TEMP_SENSOR
        ],
        ATTR_ALARM_SUPPLY_TEMP_SENSOR: [
            'Alarm Supply Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_SUPPLY_TEMP_SENSOR
        ],
        ATTR_ALARM_INDOOR_TEMP_SENSOR: [
            'Alarm Indoor Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_INDOOR_TEMP_SENSOR
        ],
        ATTR_ALARM_EXTRACT_TEMP_SENSOR: [
            'Alarm Extract Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_EXTRACT_TEMP_SENSOR
        ],
        ATTR_ALARM_PREHEATER_TEMP_SENSOR: [
            'Alarm Preheater Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_PREHEATER_TEMP_SENSOR
        ],
        ATTR_ALARM_EFFICIENCY_TEMP_SENSOR: [
            'Alarm Efficiency Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_EFFICIENCY_TEMP_SENSOR
        ],
        ATTR_ALARM_PDM_RH: [
            'Alarm PDM Relative Humidity',
            '',
            'mdi:alert',
            SENSOR_ALARM_PDM_RH
        ],
        ATTR_ALARM_PDM_TEMP: [
            'Alarm PDM Temperature Sensor',
            '',
            'mdi:alert',
            SENSOR_ALARM_PDM_TEMP
        ],
        ATTR_ALARM_CHANGE_FILTER: [
            'Alarm Filter Replacement',
            '',
            'mdi:alert',
            SENSOR_ALARM_CHANGE_FILTER
        ],
        ATTR_ALARM_EXTRA_CONTROLLER: [
            'Alarm Extra Controller Malfunction',
            '',
            'mdi:alert',
            SENSOR_ALARM_EXTRA_CONTROLLER
        ],
        ATTR_ALARM_EXTERNAL_STOP: [
            'Alarm External Stop',
            '',
            'mdi:alert',
            SENSOR_ALARM_EXTERNAL_STOP
        ],

        ATTR_ALARM_MANUAL_STOP: [
            'Alarm Stopped Manually',
            '',
            'mdi:alert',
            SENSOR_ALARM_MANUAL_STOP
        ],

        ATTR_ALARM_REHEATER_OVERHEAT: [
            'Alarm Overheated Reheater',
            '',
            'mdi:alert',
            SENSOR_ALARM_REHEATER_OVERHEAT
        ],

        ATTR_ALARM_CO2: [
            'Alarm Co2 Quality',
            '',
            'mdi:alert',
            SENSOR_ALARM_CO2
        ],

        ATTR_ALARM_RH: [
            'Alarm Humidity Quality',
            '',
            'mdi:alert',
            SENSOR_ALARM_RH
        ],

        ATTR_ALARM_INCORRECT_MANUAL_MODE: [
            'Alarm Incorrect Manual Mode',
            '',
            'mdi:alert',
            SENSOR_ALARM_INCORRECT_MANUAL_MODE
        ],

        ATTR_TARGET_TEMPERATURE: [
            'Target Temperature',
            TEMP_CELSIUS,
            'mdi:alert',
            SENSOR_TARGET_TEMPERATURE
        ]

    }

    sab = hass.data[DOMAIN]

    sensors = []
    new_sensors = {
        ATTR_EXTRACT_TEMPERATURE
    }

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        if sensor_type == "all":
            # Activate all available sensors

            for k in SENSOR_TYPES:
                new_sensors.add(k)

        elif sensor_type not in SENSOR_TYPES:
            _LOGGER.warning("Sensor type: %s is not a valid sensor.",
                            sensor_type)
            continue
        else:
            new_sensors.add(sensor_type)

    # Create sensors
    for _s in new_sensors:
        sensors.append(
            SystemAIRSensor(
                hass,
                name="%s %s" % (sab.name, SENSOR_TYPES[_s][0]),
                sab=sab,
                sensor_type=_s
            )
        )

    async_add_entities(sensors, True)


class SystemAIRSensor(Entity):
    """Representation of a ComfoConnect sensor."""

    def __init__(self, hass, name, sab: SystemAIRBridge,
                 sensor_type) -> None:
        """Initialize the SystemAIR Sensor sensor."""
        self._sab = sab
        self._sensor_type = sensor_type
        self._sensor_id = SENSOR_TYPES[self._sensor_type][3]

        self._name = name

        # Register the requested sensor
        self._sab.register_sensor(self._sensor_id)

        async def _handle_update(var):
            if var == self._sensor_id:
                self.async_schedule_update_ha_state()

        # Register for dispatcher updates
        async_dispatcher_connect(
            hass, SIGNAL_SYSTEMAIR_UPDATE_RECEIVED, _handle_update)

    @property
    def state(self):
        """Return the state of the entity."""
        try:
            return self._sab.data[self._sensor_id]

        except KeyError:
            return None

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
