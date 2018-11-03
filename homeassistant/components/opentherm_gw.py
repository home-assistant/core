"""
Support for OpenTherm Gateway devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/opentherm_gw/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as COMP_BINARY_SENSOR
from homeassistant.components.sensor import DOMAIN as COMP_SENSOR
from homeassistant.const import (CONF_DEVICE, CONF_MONITORED_VARIABLES,
                                 CONF_NAME, PRECISION_HALVES, PRECISION_TENTHS,
                                 PRECISION_WHOLE)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

import homeassistant.helpers.config_validation as cv

DOMAIN = 'opentherm_gw'

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
        vol.Optional(CONF_CLIMATE, default={}): CLIMATE_SCHEMA,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)

REQUIREMENTS = ['pyotgw==0.2b1']

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    import pyotgw
    conf = config[DOMAIN]
    gateway = pyotgw.pyotgw()
    monitored_vars = conf.get(CONF_MONITORED_VARIABLES)
    hass.data[DATA_OPENTHERM_GW] = {
        DATA_DEVICE: gateway,
        DATA_GW_VARS: pyotgw.vars,
    }
    hass.async_create_task(connect_and_subscribe(
        hass, conf[CONF_DEVICE], gateway))
    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, conf.get(CONF_CLIMATE), config))
    if monitored_vars:
        hass.async_create_task(setup_monitored_vars(
            hass, config, monitored_vars))
    return True


async def connect_and_subscribe(hass, device_path, gateway):
    """Connect to serial device and subscribe report handler."""
    await gateway.connect(hass.loop, device_path)
    _LOGGER.debug("Connected to OpenTherm Gateway at %s", device_path)

    async def handle_report(status):
        """Handle reports from the OpenTherm Gateway."""
        _LOGGER.debug("Received report: %s", status)
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    gateway.subscribe(handle_report)


async def setup_monitored_vars(hass, config, monitored_vars):
    """Set up requested sensors."""
    gw_vars = hass.data[DATA_OPENTHERM_GW][DATA_GW_VARS]
    sensor_type_map = {
        COMP_BINARY_SENSOR: [
            gw_vars.DATA_MASTER_CH_ENABLED,
            gw_vars.DATA_MASTER_DHW_ENABLED,
            gw_vars.DATA_MASTER_COOLING_ENABLED,
            gw_vars.DATA_MASTER_OTC_ENABLED,
            gw_vars.DATA_MASTER_CH2_ENABLED,
            gw_vars.DATA_SLAVE_FAULT_IND,
            gw_vars.DATA_SLAVE_CH_ACTIVE,
            gw_vars.DATA_SLAVE_DHW_ACTIVE,
            gw_vars.DATA_SLAVE_FLAME_ON,
            gw_vars.DATA_SLAVE_COOLING_ACTIVE,
            gw_vars.DATA_SLAVE_CH2_ACTIVE,
            gw_vars.DATA_SLAVE_DIAG_IND,
            gw_vars.DATA_SLAVE_DHW_PRESENT,
            gw_vars.DATA_SLAVE_CONTROL_TYPE,
            gw_vars.DATA_SLAVE_COOLING_SUPPORTED,
            gw_vars.DATA_SLAVE_DHW_CONFIG,
            gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP,
            gw_vars.DATA_SLAVE_CH2_PRESENT,
            gw_vars.DATA_SLAVE_SERVICE_REQ,
            gw_vars.DATA_SLAVE_REMOTE_RESET,
            gw_vars.DATA_SLAVE_LOW_WATER_PRESS,
            gw_vars.DATA_SLAVE_GAS_FAULT,
            gw_vars.DATA_SLAVE_AIR_PRESS_FAULT,
            gw_vars.DATA_SLAVE_WATER_OVERTEMP,
            gw_vars.DATA_REMOTE_TRANSFER_DHW,
            gw_vars.DATA_REMOTE_TRANSFER_MAX_CH,
            gw_vars.DATA_REMOTE_RW_DHW,
            gw_vars.DATA_REMOTE_RW_MAX_CH,
            gw_vars.DATA_ROVRD_MAN_PRIO,
            gw_vars.DATA_ROVRD_AUTO_PRIO,
            gw_vars.OTGW_GPIO_A_STATE,
            gw_vars.OTGW_GPIO_B_STATE,
            gw_vars.OTGW_IGNORE_TRANSITIONS,
            gw_vars.OTGW_OVRD_HB,
        ],
        COMP_SENSOR: [
            gw_vars.DATA_CONTROL_SETPOINT,
            gw_vars.DATA_MASTER_MEMBERID,
            gw_vars.DATA_SLAVE_MEMBERID,
            gw_vars.DATA_SLAVE_OEM_FAULT,
            gw_vars.DATA_COOLING_CONTROL,
            gw_vars.DATA_CONTROL_SETPOINT_2,
            gw_vars.DATA_ROOM_SETPOINT_OVRD,
            gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD,
            gw_vars.DATA_SLAVE_MAX_CAPACITY,
            gw_vars.DATA_SLAVE_MIN_MOD_LEVEL,
            gw_vars.DATA_ROOM_SETPOINT,
            gw_vars.DATA_REL_MOD_LEVEL,
            gw_vars.DATA_CH_WATER_PRESS,
            gw_vars.DATA_DHW_FLOW_RATE,
            gw_vars.DATA_ROOM_SETPOINT_2,
            gw_vars.DATA_ROOM_TEMP,
            gw_vars.DATA_CH_WATER_TEMP,
            gw_vars.DATA_DHW_TEMP,
            gw_vars.DATA_OUTSIDE_TEMP,
            gw_vars.DATA_RETURN_WATER_TEMP,
            gw_vars.DATA_SOLAR_STORAGE_TEMP,
            gw_vars.DATA_SOLAR_COLL_TEMP,
            gw_vars.DATA_CH_WATER_TEMP_2,
            gw_vars.DATA_DHW_TEMP_2,
            gw_vars.DATA_EXHAUST_TEMP,
            gw_vars.DATA_SLAVE_DHW_MAX_SETP,
            gw_vars.DATA_SLAVE_DHW_MIN_SETP,
            gw_vars.DATA_SLAVE_CH_MAX_SETP,
            gw_vars.DATA_SLAVE_CH_MIN_SETP,
            gw_vars.DATA_DHW_SETPOINT,
            gw_vars.DATA_MAX_CH_SETPOINT,
            gw_vars.DATA_OEM_DIAG,
            gw_vars.DATA_TOTAL_BURNER_STARTS,
            gw_vars.DATA_CH_PUMP_STARTS,
            gw_vars.DATA_DHW_PUMP_STARTS,
            gw_vars.DATA_DHW_BURNER_STARTS,
            gw_vars.DATA_TOTAL_BURNER_HOURS,
            gw_vars.DATA_CH_PUMP_HOURS,
            gw_vars.DATA_DHW_PUMP_HOURS,
            gw_vars.DATA_DHW_BURNER_HOURS,
            gw_vars.DATA_MASTER_OT_VERSION,
            gw_vars.DATA_SLAVE_OT_VERSION,
            gw_vars.DATA_MASTER_PRODUCT_TYPE,
            gw_vars.DATA_MASTER_PRODUCT_VERSION,
            gw_vars.DATA_SLAVE_PRODUCT_TYPE,
            gw_vars.DATA_SLAVE_PRODUCT_VERSION,
            gw_vars.OTGW_MODE,
            gw_vars.OTGW_DHW_OVRD,
            gw_vars.OTGW_ABOUT,
            gw_vars.OTGW_BUILD,
            gw_vars.OTGW_CLOCKMHZ,
            gw_vars.OTGW_LED_A,
            gw_vars.OTGW_LED_B,
            gw_vars.OTGW_LED_C,
            gw_vars.OTGW_LED_D,
            gw_vars.OTGW_LED_E,
            gw_vars.OTGW_LED_F,
            gw_vars.OTGW_GPIO_A,
            gw_vars.OTGW_GPIO_B,
            gw_vars.OTGW_SB_TEMP,
            gw_vars.OTGW_SETP_OVRD_MODE,
            gw_vars.OTGW_SMART_PWR,
            gw_vars.OTGW_THRM_DETECT,
            gw_vars.OTGW_VREF,
        ]
    }
    binary_sensors = []
    sensors = []
    for var in monitored_vars:
        if var in sensor_type_map[COMP_SENSOR]:
            sensors.append(var)
        elif var in sensor_type_map[COMP_BINARY_SENSOR]:
            binary_sensors.append(var)
        else:
            _LOGGER.error("Monitored variable not supported: %s", var)
    if binary_sensors:
        hass.async_create_task(async_load_platform(
            hass, COMP_BINARY_SENSOR, DOMAIN, binary_sensors, config))
    if sensors:
        await async_load_platform(hass, COMP_SENSOR, DOMAIN, sensors, config)
