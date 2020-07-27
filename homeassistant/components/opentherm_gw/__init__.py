"""Support for OpenTherm Gateway devices."""
import asyncio
from datetime import date, datetime
import logging

import pyotgw
import pyotgw.vars as gw_vars
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as COMP_BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as COMP_CLIMATE
from homeassistant.components.sensor import DOMAIN as COMP_SENSOR
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_DATE,
    ATTR_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_CH_OVRD,
    ATTR_DHW_OVRD,
    ATTR_GW_ID,
    ATTR_LEVEL,
    CONF_CLIMATE,
    CONF_FLOOR_TEMP,
    CONF_PRECISION,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DOMAIN,
    SERVICE_RESET_GATEWAY,
    SERVICE_SET_CH_OVRD,
    SERVICE_SET_CLOCK,
    SERVICE_SET_CONTROL_SETPOINT,
    SERVICE_SET_GPIO_MODE,
    SERVICE_SET_HOT_WATER_OVRD,
    SERVICE_SET_HOT_WATER_SETPOINT,
    SERVICE_SET_LED_MODE,
    SERVICE_SET_MAX_MOD,
    SERVICE_SET_OAT,
    SERVICE_SET_SB_TEMP,
)

_LOGGER = logging.getLogger(__name__)

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


async def options_updated(hass, entry):
    """Handle options update."""
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    async_dispatcher_send(hass, gateway.options_update_signal, entry)


async def async_setup_entry(hass, config_entry):
    """Set up the OpenTherm Gateway component."""
    if DATA_OPENTHERM_GW not in hass.data:
        hass.data[DATA_OPENTHERM_GW] = {DATA_GATEWAYS: {}}

    gateway = OpenThermGatewayDevice(hass, config_entry)
    hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]] = gateway

    config_entry.add_update_listener(options_updated)

    # Schedule directly on the loop to avoid blocking HA startup.
    hass.loop.create_task(gateway.connect_and_subscribe())

    for comp in [COMP_BINARY_SENSOR, COMP_CLIMATE, COMP_SENSOR]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, comp)
        )

    register_services(hass)
    return True


async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        conf = config[DOMAIN]
        for device_id, device_config in conf.items():
            device_config[CONF_ID] = device_id

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=device_config
                )
            )
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
    service_set_central_heating_ovrd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_CH_OVRD): cv.boolean,
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
    service_set_hot_water_setpoint_schema = service_set_control_setpoint_schema
    service_set_hot_water_ovrd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(
                cv.string, vol.In(hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS])
            ),
            vol.Required(ATTR_DHW_OVRD): vol.Any(
                vol.Equal("A"), vol.All(vol.Coerce(int), vol.Range(min=0, max=1))
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

    async def set_ch_ovrd(call):
        """Set the central heating override on the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        await gw_dev.gateway.set_ch_enable_bit(1 if call.data[ATTR_CH_OVRD] else 0)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CH_OVRD,
        set_ch_ovrd,
        service_set_central_heating_ovrd_schema,
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

    async def set_dhw_ovrd(call):
        """Set the domestic hot water override on the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gw_var = gw_vars.OTGW_DHW_OVRD
        value = await gw_dev.gateway.set_hot_water_ovrd(call.data[ATTR_DHW_OVRD])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_OVRD,
        set_dhw_ovrd,
        service_set_hot_water_ovrd_schema,
    )

    async def set_dhw_setpoint(call):
        """Set the domestic hot water setpoint on the OpenTherm Gateway."""
        gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][call.data[ATTR_GW_ID]]
        gw_var = gw_vars.DATA_DHW_SETPOINT
        value = await gw_dev.gateway.set_dhw_setpoint(call.data[ATTR_TEMPERATURE])
        gw_dev.status.update({gw_var: value})
        async_dispatcher_send(hass, gw_dev.update_signal, gw_dev.status)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SETPOINT,
        set_dhw_setpoint,
        service_set_hot_water_setpoint_schema,
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
        gpio_var = getattr(gw_vars, f"OTGW_GPIO_{gpio_id}")
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
        led_var = getattr(gw_vars, f"OTGW_LED_{led_id}")
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


async def async_unload_entry(hass, entry):
    """Cleanup and disconnect from gateway."""
    await asyncio.gather(
        hass.config_entries.async_forward_entry_unload(entry, COMP_BINARY_SENSOR),
        hass.config_entries.async_forward_entry_unload(entry, COMP_CLIMATE),
        hass.config_entries.async_forward_entry_unload(entry, COMP_SENSOR),
    )
    gateway = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][entry.data[CONF_ID]]
    await gateway.cleanup()
    return True


class OpenThermGatewayDevice:
    """OpenTherm Gateway device class."""

    def __init__(self, hass, config_entry):
        """Initialize the OpenTherm Gateway."""
        self.hass = hass
        self.device_path = config_entry.data[CONF_DEVICE]
        self.gw_id = config_entry.data[CONF_ID]
        self.name = config_entry.data[CONF_NAME]
        self.climate_config = config_entry.options
        self.status = {}
        self.update_signal = f"{DATA_OPENTHERM_GW}_{self.gw_id}_update"
        self.options_update_signal = f"{DATA_OPENTHERM_GW}_{self.gw_id}_options_update"
        self.gateway = pyotgw.pyotgw()
        self.gw_version = None

    async def cleanup(self, event=None):
        """Reset overrides on the gateway."""
        await self.gateway.set_control_setpoint(0)
        await self.gateway.set_max_relative_mod("-")
        await self.gateway.disconnect()

    async def connect_and_subscribe(self):
        """Connect to serial device and subscribe report handler."""
        self.status = await self.gateway.connect(self.hass.loop, self.device_path)
        _LOGGER.debug("Connected to OpenTherm Gateway at %s", self.device_path)
        self.gw_version = self.status.get(gw_vars.OTGW_BUILD)

        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.cleanup)

        async def handle_report(status):
            """Handle reports from the OpenTherm Gateway."""
            _LOGGER.debug("Received report: %s", status)
            self.status = status
            async_dispatcher_send(self.hass, self.update_signal, status)

        self.gateway.subscribe(handle_report)
