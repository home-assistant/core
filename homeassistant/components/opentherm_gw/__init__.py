"""Support for OpenTherm Gateway devices."""
import logging
from datetime import datetime, date

import pyotgw
import pyotgw.vars as gw_vars
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as COMP_BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as COMP_CLIMATE
from homeassistant.components.sensor import DOMAIN as COMP_SENSOR
from homeassistant.const import (
    ATTR_DATE,
    ATTR_ID,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONF_DEVICE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_GW_ID,
    ATTR_MODE,
    ATTR_LEVEL,
    CONF_CLIMATE,
    CONF_FLOOR_TEMP,
    CONF_PRECISION,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    SERVICE_RESET_GATEWAY,
    SERVICE_SET_CLOCK,
    SERVICE_SET_CONTROL_SETPOINT,
    SERVICE_SET_GPIO_MODE,
    SERVICE_SET_LED_MODE,
    SERVICE_SET_MAX_MOD,
    SERVICE_SET_OAT,
    SERVICE_SET_SB_TEMP,
)


_LOGGER = logging.getLogger(__name__)

DOMAIN = "opentherm_gw"

CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Optional(CONF_CLIMATE, default={}): CLIMATE_SCHEMA,
                vol.Optional(CONF_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    conf = config[DOMAIN]
    hass.data[DATA_OPENTHERM_GW] = {DATA_GATEWAYS: {}}
    for gw_id, cfg in conf.items():
        gateway = OpenThermGatewayDevice(hass, gw_id, cfg)
        hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][gw_id] = gateway
        hass.async_create_task(
            async_load_platform(hass, COMP_CLIMATE, DOMAIN, gw_id, config)
        )
        hass.async_create_task(
            async_load_platform(hass, COMP_BINARY_SENSOR, DOMAIN, gw_id, config)
        )
        hass.async_create_task(
            async_load_platform(hass, COMP_SENSOR, DOMAIN, gw_id, config)
        )
        # Schedule directly on the loop to avoid blocking HA startup.
        hass.loop.create_task(gateway.connect_and_subscribe(cfg[CONF_DEVICE]))
    register_services(hass)
    return True


def register_services(hass):
    """Register services for the component."""
    service_reset_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            )
        }
    )
    service_set_clock_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Optional(ATTR_DATE, default=date.today()): cv.date,
            vol.Optional(ATTR_TIME, default=datetime.now().time()): cv.time,
        }
    )
    service_set_control_setpoint_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=90)
            ),
        }
    )
    service_set_gpio_mode_schema = vol.Schema(
        vol.Any(
            vol.Schema(
                {
                    vol.Required(ATTR_GW_ID): vol.All(
                        cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
                    ),
                    vol.Required(ATTR_ID): vol.Equal("A"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=6)
                    ),
                }
            ),
            vol.Schema(
                {
                    vol.Required(ATTR_GW_ID): vol.All(
                        cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
                    ),
                    vol.Required(ATTR_ID): vol.Equal("B"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=7)
                    ),
                }
            ),
        )
    )
    service_set_led_mode_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_ID): vol.In("ABCDEF"),
            vol.Required(ATTR_MODE): vol.In("RXTBOFHWCEMP"),
        }
    )
    service_set_max_mod_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_LEVEL): vol.All(
                vol.Coerce(int), vol.Range(min=-1, max=100)
            ),
        }
    )
    service_set_oat_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=-40, max=99)
            ),
        }
    )
    service_set_sb_temp_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=30)
            ),
        }
    )

    async def reset_gateway(call):
        """Reset the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        mode_rst = gw_vars.OTGW_MODE_RESET
        status = await gw_dev.gateway.set_mode(mode_rst)
        gw_dev.status = status
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN, SERVICE_RESET_GATEWAY, reset_gateway, service_reset_schema
    )

    async def set_control_setpoint(call):
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gw_var = gw_vars.DATA_CONTROL_SETPOINT
        value = await gw_dev.gateway.set_control_setpoint(call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONTROL_SETPOINT,
        set_control_setpoint,
        service_set_control_setpoint_schema,
    )

    async def set_device_clock(call):
        """Set the clock on the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        attr_date = call.data[ATTR_DATE]
        attr_time = call.data[ATTR_TIME]
        await gw_dev.gateway.set_clock(datetime.combine(attr_date, attr_time))

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CLOCK, set_device_clock, service_set_clock_schema
    )

    async def set_gpio_mode(call):
        """Set the OpenTherm Gateway GPIO modes."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gpio_id = call.data[ATTR_ID]
        gpio_mode = call.data[ATTR_MODE]
        mode = await gw_dev.gateway.set_gpio_mode(gpio_id, gpio_mode)
        gpio_var = getattr(gw_vars, "OTGW_GPIO_{}".format(gpio_id))
        gw_dev.status.update({gpio_var: mode})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_GPIO_MODE, set_gpio_mode, service_set_gpio_mode_schema
    )

    async def set_led_mode(call):
        """Set the OpenTherm Gateway LED modes."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        led_id = call.data[ATTR_ID]
        led_mode = call.data[ATTR_MODE]
        mode = await gw_dev.gateway.set_led_mode(led_id, led_mode)
        led_var = getattr(gw_vars, "OTGW_LED_{}".format(led_id))
        gw_dev.status.update({led_var: mode})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_LED_MODE, set_led_mode, service_set_led_mode_schema
    )

    async def set_max_mod(call):
        """Set the max modulation level."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gw_var = gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD
        level = call.data[ATTR_LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = "-"
        value = await gw_dev.gateway.set_max_relative_mod(level)
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_MAX_MOD, set_max_mod, service_set_max_mod_schema
    )

    async def set_outside_temp(call):
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gw_var = gw_vars.DATA_OUTSIDE_TEMP
        value = await gw_dev.gateway.set_outside_temp(call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_OAT, set_outside_temp, service_set_oat_schema
    )

    async def set_setback_temp(call):
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gw_var = gw_vars.OTGW_SB_TEMP
        value = await gw_dev.gateway.set_setback_temp(call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SB_TEMP, set_setback_temp, service_set_sb_temp_schema
    )


class OpenThermGatewayDevice:
    """OpenTherm Gateway device class."""

    def __init__(self, hass, gw_id, config):
        """Initialize the OpenTherm Gateway."""
        self.hass = hass
        self.gw_id = gw_id
        self.name = config.get(CONF_NAME, gw_id)
        self.climate_config = config[CONF_CLIMATE]
        self.status = {}
        self.update_signal = "{}_{}_update".format(DATA_OPENTHERM_GW, gw_id)
        self.gateway = pyotgw.pyotgw()

    async def connect_and_subscribe(self, device_path):
        """Connect to serial device and subscribe report handler."""
        await self.gateway.connect(self.hass.loop, device_path)
        _LOGGER.debug("Connected to OpenTherm Gateway at %s", device_path)

        async def cleanup(event):
            """Reset overrides on the gateway."""
            await self.gateway.set_control_setpoint(0)
            await self.gateway.set_max_relative_mod("-")

        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, cleanup)

        async def handle_report(status):
            """Handle reports from the OpenTherm Gateway."""
            _LOGGER.debug("Received report: %s", status)
            self.status = status
            async_dispatcher_send(self.hass, self.update_signal, status)

        self.gateway.subscribe(handle_report)
