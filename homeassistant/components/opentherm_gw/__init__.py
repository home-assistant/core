"""Support for OpenTherm Gateway devices."""
import logging
from datetime import datetime, date

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as COMP_BINARY_SENSOR
from homeassistant.components.sensor import DOMAIN as COMP_SENSOR
from homeassistant.const import (
    ATTR_DATE, ATTR_ID, ATTR_TEMPERATURE, ATTR_TIME, CONF_DEVICE,
    CONF_MONITORED_VARIABLES, CONF_NAME, EVENT_HOMEASSISTANT_STOP,
    PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyotgw==0.4b3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'opentherm_gw'

ATTR_MODE = 'mode'
ATTR_LEVEL = 'level'

CONF_CLIMATE = 'climate'
CONF_FLOOR_TEMP = 'floor_temperature'
CONF_PRECISION = 'precision'

DATA_DEVICE = 'device'
DATA_GW_VARS = 'gw_vars'
DATA_LATEST_STATUS = 'latest_status'
DATA_OPENTHERM_GW = 'opentherm_gw'

SIGNAL_OPENTHERM_GW_UPDATE = 'opentherm_gw_update'

SERVICE_RESET_GATEWAY = 'reset_gateway'

SERVICE_SET_CLOCK = 'set_clock'
SERVICE_SET_CLOCK_SCHEMA = vol.Schema({
    vol.Optional(ATTR_DATE, default=date.today()): cv.date,
    vol.Optional(ATTR_TIME, default=datetime.now().time()): cv.time,
})

SERVICE_SET_CONTROL_SETPOINT = 'set_control_setpoint'
SERVICE_SET_CONTROL_SETPOINT_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float),
                                            vol.Range(min=0, max=90)),
})

SERVICE_SET_GPIO_MODE = 'set_gpio_mode'
SERVICE_SET_GPIO_MODE_SCHEMA = vol.Schema(vol.Any(
    vol.Schema({
        vol.Required(ATTR_ID): vol.Equal('A'),
        vol.Required(ATTR_MODE): vol.All(vol.Coerce(int),
                                         vol.Range(min=0, max=6)),
    }),
    vol.Schema({
        vol.Required(ATTR_ID): vol.Equal('B'),
        vol.Required(ATTR_MODE): vol.All(vol.Coerce(int),
                                         vol.Range(min=0, max=7)),
    }),
))

SERVICE_SET_LED_MODE = 'set_led_mode'
SERVICE_SET_LED_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ID): vol.In('ABCDEF'),
    vol.Required(ATTR_MODE): vol.In('RXTBOFHWCEMP'),
})

SERVICE_SET_MAX_MOD = 'set_max_modulation'
SERVICE_SET_MAX_MOD_SCHEMA = vol.Schema({
    vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(int),
                                      vol.Range(min=-1, max=100))
})

SERVICE_SET_OAT = 'set_outside_temperature'
SERVICE_SET_OAT_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float),
                                            vol.Range(min=-40, max=99)),
})

SERVICE_SET_SB_TEMP = 'set_setback_temperature'
SERVICE_SET_SB_TEMP_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float),
                                            vol.Range(min=0, max=30)),
})

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


async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    import pyotgw
    conf = config[DOMAIN]
    gateway = pyotgw.pyotgw()
    monitored_vars = conf.get(CONF_MONITORED_VARIABLES)
    hass.data[DATA_OPENTHERM_GW] = {
        DATA_DEVICE: gateway,
        DATA_GW_VARS: pyotgw.vars,
        DATA_LATEST_STATUS: {}
    }
    hass.async_create_task(register_services(hass, gateway))
    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, conf.get(CONF_CLIMATE), config))
    if monitored_vars:
        hass.async_create_task(setup_monitored_vars(
            hass, config, monitored_vars))
    # Schedule directly on the loop to avoid blocking HA startup.
    hass.loop.create_task(
        connect_and_subscribe(hass, conf[CONF_DEVICE], gateway))
    return True


async def connect_and_subscribe(hass, device_path, gateway):
    """Connect to serial device and subscribe report handler."""
    await gateway.connect(hass.loop, device_path)
    _LOGGER.debug("Connected to OpenTherm Gateway at %s", device_path)

    async def cleanup(event):
        """Reset overrides on the gateway."""
        await gateway.set_control_setpoint(0)
        await gateway.set_max_relative_mod('-')
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, cleanup)

    async def handle_report(status):
        """Handle reports from the OpenTherm Gateway."""
        _LOGGER.debug("Received report: %s", status)
        hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS] = status
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    gateway.subscribe(handle_report)


async def register_services(hass, gateway):
    """Register services for the component."""
    gw_vars = hass.data[DATA_OPENTHERM_GW][DATA_GW_VARS]

    async def reset_gateway(call):
        """Reset the OpenTherm Gateway."""
        mode_rst = gw_vars.OTGW_MODE_RESET
        status = await gateway.set_mode(mode_rst)
        hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS] = status
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_RESET_GATEWAY, reset_gateway)

    async def set_control_setpoint(call):
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_var = gw_vars.DATA_CONTROL_SETPOINT
        value = await gateway.set_control_setpoint(call.data[ATTR_TEMPERATURE])
        status = hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS]
        status.update({gw_var: value})
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_SET_CONTROL_SETPOINT,
                                 set_control_setpoint,
                                 SERVICE_SET_CONTROL_SETPOINT_SCHEMA)

    async def set_device_clock(call):
        """Set the clock on the OpenTherm Gateway."""
        attr_date = call.data[ATTR_DATE]
        attr_time = call.data[ATTR_TIME]
        await gateway.set_clock(datetime.combine(attr_date, attr_time))
    hass.services.async_register(DOMAIN, SERVICE_SET_CLOCK, set_device_clock,
                                 SERVICE_SET_CLOCK_SCHEMA)

    async def set_gpio_mode(call):
        """Set the OpenTherm Gateway GPIO modes."""
        gpio_id = call.data[ATTR_ID]
        gpio_mode = call.data[ATTR_MODE]
        mode = await gateway.set_gpio_mode(gpio_id, gpio_mode)
        gpio_var = getattr(gw_vars, 'OTGW_GPIO_{}'.format(gpio_id))
        status = hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS]
        status.update({gpio_var: mode})
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_SET_GPIO_MODE, set_gpio_mode,
                                 SERVICE_SET_GPIO_MODE_SCHEMA)

    async def set_led_mode(call):
        """Set the OpenTherm Gateway LED modes."""
        led_id = call.data[ATTR_ID]
        led_mode = call.data[ATTR_MODE]
        mode = await gateway.set_led_mode(led_id, led_mode)
        led_var = getattr(gw_vars, 'OTGW_LED_{}'.format(led_id))
        status = hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS]
        status.update({led_var: mode})
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_SET_LED_MODE, set_led_mode,
                                 SERVICE_SET_LED_MODE_SCHEMA)

    async def set_max_mod(call):
        """Set the max modulation level."""
        gw_var = gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD
        level = call.data[ATTR_LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = '-'
        value = await gateway.set_max_relative_mod(level)
        status = hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS]
        status.update({gw_var: value})
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_SET_MAX_MOD, set_max_mod,
                                 SERVICE_SET_MAX_MOD_SCHEMA)

    async def set_outside_temp(call):
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_var = gw_vars.DATA_OUTSIDE_TEMP
        value = await gateway.set_outside_temp(call.data[ATTR_TEMPERATURE])
        status = hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS]
        status.update({gw_var: value})
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_SET_OAT, set_outside_temp,
                                 SERVICE_SET_OAT_SCHEMA)

    async def set_setback_temp(call):
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_var = gw_vars.OTGW_SB_TEMP
        value = await gateway.set_setback_temp(call.data[ATTR_TEMPERATURE])
        status = hass.data[DATA_OPENTHERM_GW][DATA_LATEST_STATUS]
        status.update({gw_var: value})
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    hass.services.async_register(DOMAIN, SERVICE_SET_SB_TEMP, set_setback_temp,
                                 SERVICE_SET_SB_TEMP_SCHEMA)


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
        hass.async_create_task(async_load_platform(
            hass, COMP_SENSOR, DOMAIN, sensors, config))
