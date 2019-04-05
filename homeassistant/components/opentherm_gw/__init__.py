"""Support for OpenTherm Gateway devices."""
import logging
from datetime import datetime, date

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as COMP_BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as COMP_CLIMATE
from homeassistant.components.sensor import DOMAIN as COMP_SENSOR
from homeassistant.const import (
    ATTR_DATE, ATTR_ID, ATTR_TEMPERATURE, ATTR_TIME, CONF_DEVICE,
    CONF_MONITORED_VARIABLES, CONF_NAME, EVENT_HOMEASSISTANT_STOP,
    PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'opentherm_gw'

ATTR_GW_ID = 'gateway_id'
ATTR_MODE = 'mode'
ATTR_LEVEL = 'level'

CONF_CLIMATE = 'climate'
CONF_FLOOR_TEMP = 'floor_temperature'
CONF_PRECISION = 'precision'

DATA_DEVICE = 'device'
DATA_GATEWAYS = 'gateways'
DATA_GW_VARS = 'gw_vars'
DATA_LATEST_STATUS = 'latest_status'
DATA_OPENTHERM_GW = 'opentherm_gw'

SERVICE_RESET_GATEWAY = 'reset_gateway'
SERVICE_SET_CLOCK = 'set_clock'
SERVICE_SET_CONTROL_SETPOINT = 'set_control_setpoint'
SERVICE_SET_GPIO_MODE = 'set_gpio_mode'
SERVICE_SET_LED_MODE = 'set_led_mode'
SERVICE_SET_MAX_MOD = 'set_max_modulation'
SERVICE_SET_OAT = 'set_outside_temperature'
SERVICE_SET_SB_TEMP = 'set_setback_temperature'

CLIMATE_SCHEMA = vol.Schema({
    vol.Optional(CONF_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES,
                                          PRECISION_WHOLE]),
    vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_CLIMATE, default={}): CLIMATE_SCHEMA,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): [cv.string],
        vol.Optional(CONF_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    conf = config[DOMAIN]
    hass.data[DATA_OPENTHERM_GW] = {DATA_GATEWAYS: {}}
    for gw_id, cfg in conf.items():
        gateway = OpenThermGatewayDevice(hass, gw_id, cfg, config)
        hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][gw_id] = gateway
    hass.async_create_task(register_services(hass))
    return True


async def register_services(hass):
    """Register services for the component."""
    import pyotgw.vars as gw_vars
    service_reset_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
    })
    service_set_clock_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
        vol.Optional(ATTR_DATE, default=date.today()): cv.date,
        vol.Optional(ATTR_TIME, default=datetime.now().time()): cv.time,
    })
    service_set_control_setpoint_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
        vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float),
                                                vol.Range(min=0, max=90)),
    })
    service_set_gpio_mode_schema = vol.Schema(vol.Any(
        vol.Schema({
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(
                    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
            vol.Required(ATTR_ID): vol.Equal('A'),
            vol.Required(ATTR_MODE): vol.All(vol.Coerce(int),
                                             vol.Range(min=0, max=6)),
        }),
        vol.Schema({
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(
                    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
            vol.Required(ATTR_ID): vol.Equal('B'),
            vol.Required(ATTR_MODE): vol.All(vol.Coerce(int),
                                             vol.Range(min=0, max=7)),
        }),
    ))
    service_set_led_mode_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
        vol.Required(ATTR_ID): vol.In('ABCDEF'),
        vol.Required(ATTR_MODE): vol.In('RXTBOFHWCEMP'),
    })
    service_set_max_mod_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
        vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(int),
                                          vol.Range(min=-1, max=100))
    })
    service_set_oat_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
        vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float),
                                                vol.Range(min=-40, max=99)),
    })
    service_set_sb_temp_schema = vol.Schema({
        vol.Required(ATTR_GW_ID): vol.All(
            cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])),
        vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float),
                                                vol.Range(min=0, max=30)),
    })

    async def reset_gateway(call):
        """Reset the OpenTherm Gateway."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        mode_rst = gw_vars.OTGW_MODE_RESET
        status = await gw_dev.gateway.set_mode(mode_rst)
        gw_dev.status = status
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_RESET_GATEWAY, reset_gateway,
                                 service_reset_schema)

    async def set_control_setpoint(call):
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        gw_var = gw_vars.DATA_CONTROL_SETPOINT
        value = await gw_dev.gateway.set_control_setpoint(
            call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_SET_CONTROL_SETPOINT,
                                 set_control_setpoint,
                                 service_set_control_setpoint_schema)

    async def set_device_clock(call):
        """Set the clock on the OpenTherm Gateway."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        attr_date = call.data[ATTR_DATE]
        attr_time = call.data[ATTR_TIME]
        await gw_dev.gateway.set_clock(datetime.combine(attr_date, attr_time))
    hass.services.async_register(DOMAIN, SERVICE_SET_CLOCK, set_device_clock,
                                 service_set_clock_schema)

    async def set_gpio_mode(call):
        """Set the OpenTherm Gateway GPIO modes."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        gpio_id = call.data[ATTR_ID]
        gpio_mode = call.data[ATTR_MODE]
        mode = await gw_dev.gateway.set_gpio_mode(gpio_id, gpio_mode)
        gpio_var = getattr(gw_vars, 'OTGW_GPIO_{}'.format(gpio_id))
        gw_dev.status.update({gpio_var: mode})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_SET_GPIO_MODE, set_gpio_mode,
                                 service_set_gpio_mode_schema)

    async def set_led_mode(call):
        """Set the OpenTherm Gateway LED modes."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        led_id = call.data[ATTR_ID]
        led_mode = call.data[ATTR_MODE]
        mode = await gw_dev.gateway.set_led_mode(led_id, led_mode)
        led_var = getattr(gw_vars, 'OTGW_LED_{}'.format(led_id))
        gw_dev.status.update({led_var: mode})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_SET_LED_MODE, set_led_mode,
                                 service_set_led_mode_schema)

    async def set_max_mod(call):
        """Set the max modulation level."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        gw_var = gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD
        level = call.data[ATTR_LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = '-'
        value = await gw_dev.gateway.set_max_relative_mod(level)
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_SET_MAX_MOD, set_max_mod,
                                 service_set_max_mod_schema)

    async def set_outside_temp(call):
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        gw_var = gw_vars.DATA_OUTSIDE_TEMP
        value = await gw_dev.gateway.set_outside_temp(
            call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_SET_OAT, set_outside_temp,
                                 service_set_oat_schema)

    async def set_setback_temp(call):
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_dev = (
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]])
        gw_var = gw_vars.OTGW_SB_TEMP
        value = await gw_dev.gateway.set_setback_temp(
            call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)
    hass.services.async_register(DOMAIN, SERVICE_SET_SB_TEMP, set_setback_temp,
                                 service_set_sb_temp_schema)


class OpenThermGatewayDevice():
    """OpenTherm Gateway device class."""

    def __init__(self, hass, gw_id, config, hass_config):
        """Initialize the OpenTherm Gateway."""
        import pyotgw
        self.hass = hass
        self.gw_id = gw_id
        self.name = config.get(CONF_NAME, gw_id)
        self.climate_config = config[CONF_CLIMATE]
        self.binary_sensors = []
        self.sensors = []
        self.status = {}
        self.update_signal = '{}_{}_update'.format(DATA_OPENTHERM_GW, gw_id)
        self.gateway = pyotgw.pyotgw()
        self.vars = pyotgw.vars
        hass.async_create_task(async_load_platform(hass, COMP_CLIMATE, DOMAIN,
                                                   self.gw_id, hass_config))
        monitored_vars = config[CONF_MONITORED_VARIABLES]
        if monitored_vars:
            hass.async_create_task(
                self.setup_monitored_vars(monitored_vars, hass_config))
        # Schedule directly on the loop to avoid blocking HA startup.
        hass.loop.create_task(self.connect_and_subscribe(config[CONF_DEVICE]))

    async def connect_and_subscribe(self, device_path):
        """Connect to serial device and subscribe report handler."""
        await self.gateway.connect(self.hass.loop, device_path)
        _LOGGER.debug("Connected to OpenTherm Gateway at %s", device_path)

        async def cleanup(event):
            """Reset overrides on the gateway."""
            await self.gateway.set_control_setpoint(0)
            await self.gateway.set_max_relative_mod('-')
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, cleanup)

        async def handle_report(status):
            """Handle reports from the OpenTherm Gateway."""
            _LOGGER.debug("Received report: %s", status)
            self.status = status
            async_dispatcher_send(self.hass, self.update_signal, status)
        self.gateway.subscribe(handle_report)

    async def setup_monitored_vars(self, monitored_vars, hass_config):
        """Set up requested sensors."""
        sensor_type_map = {
            COMP_BINARY_SENSOR: [
                self.vars.DATA_MASTER_CH_ENABLED,
                self.vars.DATA_MASTER_DHW_ENABLED,
                self.vars.DATA_MASTER_COOLING_ENABLED,
                self.vars.DATA_MASTER_OTC_ENABLED,
                self.vars.DATA_MASTER_CH2_ENABLED,
                self.vars.DATA_SLAVE_FAULT_IND,
                self.vars.DATA_SLAVE_CH_ACTIVE,
                self.vars.DATA_SLAVE_DHW_ACTIVE,
                self.vars.DATA_SLAVE_FLAME_ON,
                self.vars.DATA_SLAVE_COOLING_ACTIVE,
                self.vars.DATA_SLAVE_CH2_ACTIVE,
                self.vars.DATA_SLAVE_DIAG_IND,
                self.vars.DATA_SLAVE_DHW_PRESENT,
                self.vars.DATA_SLAVE_CONTROL_TYPE,
                self.vars.DATA_SLAVE_COOLING_SUPPORTED,
                self.vars.DATA_SLAVE_DHW_CONFIG,
                self.vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP,
                self.vars.DATA_SLAVE_CH2_PRESENT,
                self.vars.DATA_SLAVE_SERVICE_REQ,
                self.vars.DATA_SLAVE_REMOTE_RESET,
                self.vars.DATA_SLAVE_LOW_WATER_PRESS,
                self.vars.DATA_SLAVE_GAS_FAULT,
                self.vars.DATA_SLAVE_AIR_PRESS_FAULT,
                self.vars.DATA_SLAVE_WATER_OVERTEMP,
                self.vars.DATA_REMOTE_TRANSFER_DHW,
                self.vars.DATA_REMOTE_TRANSFER_MAX_CH,
                self.vars.DATA_REMOTE_RW_DHW,
                self.vars.DATA_REMOTE_RW_MAX_CH,
                self.vars.DATA_ROVRD_MAN_PRIO,
                self.vars.DATA_ROVRD_AUTO_PRIO,
                self.vars.OTGW_GPIO_A_STATE,
                self.vars.OTGW_GPIO_B_STATE,
                self.vars.OTGW_IGNORE_TRANSITIONS,
                self.vars.OTGW_OVRD_HB,
            ],
            COMP_SENSOR: [
                self.vars.DATA_CONTROL_SETPOINT,
                self.vars.DATA_MASTER_MEMBERID,
                self.vars.DATA_SLAVE_MEMBERID,
                self.vars.DATA_SLAVE_OEM_FAULT,
                self.vars.DATA_COOLING_CONTROL,
                self.vars.DATA_CONTROL_SETPOINT_2,
                self.vars.DATA_ROOM_SETPOINT_OVRD,
                self.vars.DATA_SLAVE_MAX_RELATIVE_MOD,
                self.vars.DATA_SLAVE_MAX_CAPACITY,
                self.vars.DATA_SLAVE_MIN_MOD_LEVEL,
                self.vars.DATA_ROOM_SETPOINT,
                self.vars.DATA_REL_MOD_LEVEL,
                self.vars.DATA_CH_WATER_PRESS,
                self.vars.DATA_DHW_FLOW_RATE,
                self.vars.DATA_ROOM_SETPOINT_2,
                self.vars.DATA_ROOM_TEMP,
                self.vars.DATA_CH_WATER_TEMP,
                self.vars.DATA_DHW_TEMP,
                self.vars.DATA_OUTSIDE_TEMP,
                self.vars.DATA_RETURN_WATER_TEMP,
                self.vars.DATA_SOLAR_STORAGE_TEMP,
                self.vars.DATA_SOLAR_COLL_TEMP,
                self.vars.DATA_CH_WATER_TEMP_2,
                self.vars.DATA_DHW_TEMP_2,
                self.vars.DATA_EXHAUST_TEMP,
                self.vars.DATA_SLAVE_DHW_MAX_SETP,
                self.vars.DATA_SLAVE_DHW_MIN_SETP,
                self.vars.DATA_SLAVE_CH_MAX_SETP,
                self.vars.DATA_SLAVE_CH_MIN_SETP,
                self.vars.DATA_DHW_SETPOINT,
                self.vars.DATA_MAX_CH_SETPOINT,
                self.vars.DATA_OEM_DIAG,
                self.vars.DATA_TOTAL_BURNER_STARTS,
                self.vars.DATA_CH_PUMP_STARTS,
                self.vars.DATA_DHW_PUMP_STARTS,
                self.vars.DATA_DHW_BURNER_STARTS,
                self.vars.DATA_TOTAL_BURNER_HOURS,
                self.vars.DATA_CH_PUMP_HOURS,
                self.vars.DATA_DHW_PUMP_HOURS,
                self.vars.DATA_DHW_BURNER_HOURS,
                self.vars.DATA_MASTER_OT_VERSION,
                self.vars.DATA_SLAVE_OT_VERSION,
                self.vars.DATA_MASTER_PRODUCT_TYPE,
                self.vars.DATA_MASTER_PRODUCT_VERSION,
                self.vars.DATA_SLAVE_PRODUCT_TYPE,
                self.vars.DATA_SLAVE_PRODUCT_VERSION,
                self.vars.OTGW_MODE,
                self.vars.OTGW_DHW_OVRD,
                self.vars.OTGW_ABOUT,
                self.vars.OTGW_BUILD,
                self.vars.OTGW_CLOCKMHZ,
                self.vars.OTGW_LED_A,
                self.vars.OTGW_LED_B,
                self.vars.OTGW_LED_C,
                self.vars.OTGW_LED_D,
                self.vars.OTGW_LED_E,
                self.vars.OTGW_LED_F,
                self.vars.OTGW_GPIO_A,
                self.vars.OTGW_GPIO_B,
                self.vars.OTGW_SB_TEMP,
                self.vars.OTGW_SETP_OVRD_MODE,
                self.vars.OTGW_SMART_PWR,
                self.vars.OTGW_THRM_DETECT,
                self.vars.OTGW_VREF,
            ]
        }
        for var in monitored_vars:
            if var in sensor_type_map[COMP_SENSOR]:
                self.sensors.append(var)
            elif var in sensor_type_map[COMP_BINARY_SENSOR]:
                self.binary_sensors.append(var)
            else:
                _LOGGER.error("Monitored variable not supported: %s", var)
        if self.binary_sensors:
            self.hass.async_create_task(async_load_platform(
                self.hass, COMP_BINARY_SENSOR, DOMAIN, self.gw_id,
                hass_config))
        if self.sensors:
            self.hass.async_create_task(async_load_platform(
                self.hass, COMP_SENSOR, DOMAIN, self.gw_id, hass_config))
