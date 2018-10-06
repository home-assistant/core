"""
Support for OpenTherm Gateway devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/opentherm_gw/
"""
import logging
import voluptuous as vol

from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import (CONF_DEVICE, CONF_MONITORED_VARIABLES,
                                 CONF_NAME, PRECISION_HALVES, PRECISION_TENTHS,
                                 PRECISION_WHOLE)
import homeassistant.helpers.config_validation as cv

DOMAIN = 'opentherm_gw'

COMP_SENSOR = 'sensor'
COMP_BINARY_SENSOR = 'binary_sensor'

CONF_CLIMATE = 'climate'
CONF_FLOOR_TEMP = 'floor_temperature'
CONF_PRECISION = 'precision'

DATA_DEVICE = 'device'
DATA_GW_VARS = 'gw_vars'
DATA_OPENTHERM_GW = 'opentherm_gw'

SIGNAL_OPENTHERM_GW_UPDATE = 'opentherm_gw_update'

CLIMATE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default="OpenTherm Gateway"): cv.string,
    vol.Optional(CONF_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES,
                                          PRECISION_WHOLE]),
    vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_CLIMATE, default=CLIMATE_SCHEMA({})):
            CLIMATE_SCHEMA,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): cv.ensure_list,
    }),
}, extra=vol.ALLOW_EXTRA)

REQUIREMENTS = ['pyotgw==0.1b0']

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    import pyotgw
    hass.data[DATA_OPENTHERM_GW] = {
        DATA_DEVICE: pyotgw.pyotgw(),
        DATA_GW_VARS: pyotgw.vars,
    }
    hass.async_add_job(connect_and_subscribe, hass, conf)
    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, conf.get(CONF_CLIMATE)))
    hass.async_add_job(setup_monitored_vars, hass,
                       conf.get(CONF_MONITORED_VARIABLES))
    return True


async def connect_and_subscribe(hass, conf):
    """Connect to serial device and subscribe report handler."""
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_DEVICE]
    await gateway.connect(hass.loop, conf[CONF_DEVICE])

    async def handle_report(status):
        """Handle reports from the OpenTherm Gateway."""
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    gateway.subscribe(handle_report)

async def setup_monitored_vars(hass, monitored_vars):
    """Setup requested sensors and binary_sensors."""
    gw_vars = hass.data[DATA_OPENTHERM_GW][DATA_GW_VARS]
    sensor_type_map = {
        gw_vars.DATA_MASTER_CH_ENABLED: COMP_BINARY_SENSOR,
        gw_vars.DATA_MASTER_DHW_ENABLED: COMP_BINARY_SENSOR,
        gw_vars.DATA_MASTER_COOLING_ENABLED: COMP_BINARY_SENSOR,
        gw_vars.DATA_MASTER_OTC_ENABLED: COMP_BINARY_SENSOR,
        gw_vars.DATA_MASTER_CH2_ENABLED: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_FAULT_IND: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_CH_ACTIVE: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_DHW_ACTIVE: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_FLAME_ON: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_COOLING_ACTIVE: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_CH2_ACTIVE: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_DIAG_IND: COMP_BINARY_SENSOR,
        gw_vars.DATA_CONTROL_SETPOINT: COMP_SENSOR,
        gw_vars.DATA_MASTER_MEMBERID: COMP_SENSOR,
        gw_vars.DATA_SLAVE_DHW_PRESENT: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_CONTROL_TYPE: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_COOLING_SUPPORTED: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_DHW_CONFIG: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_CH2_PRESENT: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_MEMBERID: COMP_SENSOR,
        gw_vars.DATA_SLAVE_SERVICE_REQ: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_REMOTE_RESET: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_LOW_WATER_PRESS: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_GAS_FAULT: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_AIR_PRESS_FAULT: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_WATER_OVERTEMP: COMP_BINARY_SENSOR,
        gw_vars.DATA_SLAVE_OEM_FAULT: COMP_SENSOR,
        gw_vars.DATA_REMOTE_TRANSFER_DHW: COMP_BINARY_SENSOR,
        gw_vars.DATA_REMOTE_TRANSFER_MAX_CH: COMP_BINARY_SENSOR,
        gw_vars.DATA_REMOTE_RW_DHW: COMP_BINARY_SENSOR,
        gw_vars.DATA_REMOTE_RW_MAX_CH: COMP_BINARY_SENSOR,
        gw_vars.DATA_COOLING_CONTROL: COMP_SENSOR,
        gw_vars.DATA_CONTROL_SETPOINT_2: COMP_SENSOR,
        gw_vars.DATA_ROOM_SETPOINT_OVRD: COMP_SENSOR,
        gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD: COMP_SENSOR,
        gw_vars.DATA_SLAVE_MAX_CAPACITY: COMP_SENSOR,
        gw_vars.DATA_SLAVE_MIN_MOD_LEVEL: COMP_SENSOR,
        gw_vars.DATA_ROOM_SETPOINT: COMP_SENSOR,
        gw_vars.DATA_REL_MOD_LEVEL: COMP_SENSOR,
        gw_vars.DATA_CH_WATER_PRESS: COMP_SENSOR,
        gw_vars.DATA_DHW_FLOW_RATE: COMP_SENSOR,
        gw_vars.DATA_ROOM_SETPOINT_2: COMP_SENSOR,
        gw_vars.DATA_ROOM_TEMP: COMP_SENSOR,
        gw_vars.DATA_CH_WATER_TEMP: COMP_SENSOR,
        gw_vars.DATA_DHW_TEMP: COMP_SENSOR,
        gw_vars.DATA_OUTSIDE_TEMP: COMP_SENSOR,
        gw_vars.DATA_RETURN_WATER_TEMP: COMP_SENSOR,
        gw_vars.DATA_SOLAR_STORAGE_TEMP: COMP_SENSOR,
        gw_vars.DATA_SOLAR_COLL_TEMP: COMP_SENSOR,
        gw_vars.DATA_CH_WATER_TEMP_2: COMP_SENSOR,
        gw_vars.DATA_DHW_TEMP_2: COMP_SENSOR,
        gw_vars.DATA_EXHAUST_TEMP: COMP_SENSOR,
        gw_vars.DATA_SLAVE_DHW_MAX_SETP: COMP_SENSOR,
        gw_vars.DATA_SLAVE_DHW_MIN_SETP: COMP_SENSOR,
        gw_vars.DATA_SLAVE_CH_MAX_SETP: COMP_SENSOR,
        gw_vars.DATA_SLAVE_CH_MIN_SETP: COMP_SENSOR,
        gw_vars.DATA_DHW_SETPOINT: COMP_SENSOR,
        gw_vars.DATA_MAX_CH_SETPOINT: COMP_SENSOR,
        gw_vars.DATA_ROVRD_MAN_PRIO: COMP_BINARY_SENSOR,
        gw_vars.DATA_ROVRD_AUTO_PRIO: COMP_BINARY_SENSOR,
        gw_vars.DATA_OEM_DIAG: COMP_SENSOR,
        gw_vars.DATA_CH_BURNER_STARTS: COMP_SENSOR,
        gw_vars.DATA_CH_PUMP_STARTS: COMP_SENSOR,
        gw_vars.DATA_DHW_PUMP_STARTS: COMP_SENSOR,
        gw_vars.DATA_DHW_BURNER_STARTS: COMP_SENSOR,
        gw_vars.DATA_CH_BURNER_HOURS: COMP_SENSOR,
        gw_vars.DATA_CH_PUMP_HOURS: COMP_SENSOR,
        gw_vars.DATA_DHW_PUMP_HOURS: COMP_SENSOR,
        gw_vars.DATA_DHW_BURNER_HOURS: COMP_SENSOR,
        gw_vars.DATA_MASTER_OT_VERSION: COMP_SENSOR,
        gw_vars.DATA_SLAVE_OT_VERSION: COMP_SENSOR,
        gw_vars.DATA_MASTER_PRODUCT_TYPE: COMP_SENSOR,
        gw_vars.DATA_MASTER_PRODUCT_VERSION: COMP_SENSOR,
        gw_vars.DATA_SLAVE_PRODUCT_TYPE: COMP_SENSOR,
        gw_vars.DATA_SLAVE_PRODUCT_VERSION: COMP_SENSOR,
    }
    sensors = {COMP_SENSOR: [], COMP_BINARY_SENSOR: []}
    for var in monitored_vars:
        if var not in sensor_type_map:
            _LOGGER.error("Monitored variable not supported: %s", var)
            continue
        sensors[sensor_type_map[var]].append(var)
    if sensors[COMP_SENSOR]:
        hass.async_create_task(async_load_platform(
            hass, COMP_SENSOR, DOMAIN, sensors[COMP_SENSOR]))
    if sensors[COMP_BINARY_SENSOR]:
        hass.async_create_task(async_load_platform(
            hass, COMP_BINARY_SENSOR, DOMAIN, sensors[COMP_BINARY_SENSOR]))
