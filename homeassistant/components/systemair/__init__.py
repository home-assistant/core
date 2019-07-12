"""Support for the SystemAIR ventilation units."""

import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_ID, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'systemair'

SIGNAL_SYSTEMAIR_UPDATE_RECEIVED = 'systemair_update_received'
SIGNAL_SYSTEMAIR_UPDATE_DONE = 'systemair_update_done'

DEFAULT_NAME = "SystemAIR"

DEVICE = None

# Presets
PRESET_AUTO = 'auto'
PRESET_MANUAL = 'manual'
PRESET_CROWDED = 'crowded'
PRESET_REFRESH = 'refresh'
PRESET_FIREPLACE = 'fireplace'
PRESET_HOLIDAY = 'holiday'
PRESET_IDLE = 'idle'


# Fan
ATTR_FAN_SPEED_EXTRACT = 'fan_speed_extract'
ATTR_FAN_SPEED_SUPPLY = 'fan_speed_supply'


# Temperature
ATTR_OUTSIDE_TEMPERATURE = 'temperature_outside'
ATTR_SUPPLY_TEMPERATURE = 'temperature_supply'
ATTR_EXTRACT_TEMPERATURE = 'temperature_extract'

# Humidity
ATTR_CURRENT_HUMIDITY = 'current_humidity'

# Filter
ATTR_FILTER_TIME = 'change_filter_timestamp'

# Fan mode
ATTR_CURRENT_FAN_MODE = 'fan_mode'

# Operation
ATTR_CURRENT_OPERATION = "operation_mode"

# User Lock
ATTR_USER_LOCK = "user_lock"

# Activated ventilation functions
ATTR_FUNCTION_COOLING = 'function_cooling'
ATTR_FUNCTION_VACUUM_CLEANER = 'function_vacuum_cleaner'
ATTR_FUNCTION_FREE_COOLING = 'function_free_cooling'
ATTR_FUNCTION_HEATING = 'function_heating'
ATTR_FUNCTION_DEFROSTING = 'function_defrosting'
ATTR_FUNCTION_HEAT_RECOVERY = 'function_heat_recovery'
ATTR_FUNCTION_COOLING_RECOVERY = 'function_cooling_recovery'
ATTR_FUNCTION_MOISTURE_TRANSFER = 'function_moisture_transfer'
ATTR_FUNCTION_SECONDARY_AIR = 'function_secondary_air'
ATTR_FUNCTION_COOKER_HOOD = 'function_cooker_hood'
ATTR_FUNCTION_HEATER_COOLDOWN = 'function_heater_cooldown'
ATTR_FUNCTION_SERVICE_USER_LOCK = 'function_service_user_lock'


# Alarms
ATTR_ALARM_FROST_PROTECTION = 'alarm_frost_prot'
ATTR_ALARM_FROST_PROTECTION_SENSOR = 'alarm_fpt'
ATTR_ALARM_DEFROST = 'alarm_defrosting'
ATTR_ALARM_SUPPLY_RPM = 'alarm_saf_rpm'
ATTR_ALARM_EXTRACT_RPM = 'alarm_eaf_rpm'
ATTR_ALARM_SUPPLY_FLOW_PRESSURE = 'alarm_saf_ctrl'
ATTR_ALARM_EXTRACT_FLOW_PRESSURE = 'alarm_eaf_ctrl'
ATTR_ALARM_ELECTRICAL_HEATER = 'alarm_emt'
ATTR_ALARM_BYPASS_DAMPER = 'alarm_bys'
ATTR_ALARM_ROTARY_EXCHANGER = 'alarm_rgs'
ATTR_ALARM_BYPASS_DAMPER_2 = 'alarm_secondary_air'
ATTR_ALARM_OUTDOOR_TEMP_SENSOR = 'alarm_oat'
ATTR_ALARM_REHEATER_TEMP_SENSOR = 'alarm_oht'
ATTR_ALARM_SUPPLY_TEMP_SENSOR = 'alarm_sat'
ATTR_ALARM_INDOOR_TEMP_SENSOR = 'alarm_rat'
ATTR_ALARM_EXTRACT_TEMP_SENSOR = 'alarm_eat'
ATTR_ALARM_PREHEATER_TEMP_SENSOR = 'alarm_ect'
ATTR_ALARM_EFFICIENCY_TEMP_SENSOR = 'alarm_eft'
ATTR_ALARM_PDM_RH = 'alarm_pdm_rhs'
ATTR_ALARM_PDM_TEMP = 'alarm_pdm_eat'
ATTR_ALARM_CHANGE_FILTER = 'alarm_filter'
ATTR_ALARM_EXTRA_CONTROLLER = 'alarm_extra_controller'  #
ATTR_ALARM_EXTERNAL_STOP = 'alarm_external_stop'
ATTR_ALARM_MANUAL_STOP = 'alarm_manual_fan_stop'
ATTR_ALARM_REHEATER_OVERHEAT = 'alarm_overheat_temperature'
ATTR_ALARM_SUPPLY_TEMP_LOW = 'alarm_low_sat'
ATTR_ALARM_CO2 = 'alarm_co2'
ATTR_ALARM_RH = 'alarm_rh'
ATTR_ALARM_INCORRECT_MANUAL_MODE = 'alarm_manual_mode'

# Rear / Write
ATTR_TARGET_TEMPERATURE = "main_temperature_offset"

COMPONENT_TYPES = ['climate', 'sensor']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL,
                     default=DEFAULT_SCAN_INTERVAL): cv.timedelta,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,

    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the SystemAIR bridge."""
    conf = config[DOMAIN]

    iam_id = conf.get(CONF_ID)
    password = conf.get(CONF_PASSWORD)
    name = conf.get(CONF_NAME)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    # Setup ComfoConnect Bridge
    sab = SystemAIRBridge(hass, iam_id, password, name, scan_interval)
    hass.data[DOMAIN] = sab
    # Start connection with bridge
    await sab.connect()

    # Schedule disconnect on shutdown
    async def _shutdown(_event):
        await sab.shutdown()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    return True


class SystemAIRBridge:
    """SystemAIR Savecair API bridge."""

    def __init__(self, hass, iam_id, password, name, scan_interval):
        """Initialize the Savecair API bridge."""
        from systemair.savecair.systemair import SystemAIR

        self.hass = hass
        self.data = {}
        self.name = name
        self.hass = hass

        self.systemair = SystemAIR(
            iam_id=iam_id,
            password=password,
            loop=hass.loop,
            update_interval=scan_interval.seconds
        )

        self.systemair.on_update.append(self.on_sensor_update)
        self.systemair.on_update_done.append(self.on_sensor_update_done)

    async def connect(self):
        """Connect to the SystemAIR Endpoint."""
        await self.systemair.connect()

    async def shutdown(self):
        """Disconnect and Shutdowns the SystemAIR application."""
        await self.systemair.shutdown()

    async def on_sensor_update(self, var, value):
        """Sensor update callback."""
        self.data[var] = value
        async_dispatcher_send(self.hass, SIGNAL_SYSTEMAIR_UPDATE_RECEIVED, var)

    async def on_sensor_update_done(self, data):
        """Completed sensor update callback."""
        self.data.update(data)
        async_dispatcher_send(self.hass, SIGNAL_SYSTEMAIR_UPDATE_DONE, data)

    def register_sensor(self, sensor_name):
        """Register a sensor to the endpoint."""
        _LOGGER.debug("Subscribed to sensor: %s", sensor_name)
        self.systemair.subscribe(sensor_name)

    async def update(self):
        """Poll a update from the sensors."""
        await self.systemair.update_sensors()

    async def set(self, k, _v):
        """Set a value for the SystemAIR endpoint based on a key."""
        await self.systemair.set(k, _v)
