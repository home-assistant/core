"""Support for OpenTherm Gateway devices."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import pyotgw.vars as gw_vars
import voluptuous as vol

from homeassistant.const import (
    ATTR_DATE,
    ATTR_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_TIME,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CH_OVRD,
    ATTR_DHW_OVRD,
    ATTR_GW_ID,
    ATTR_LEVEL,
    ATTR_TRANSP_ARG,
    ATTR_TRANSP_CMD,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DOMAIN,
    SERVICE_RESET_GATEWAY,
    SERVICE_SEND_TRANSP_CMD,
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

if TYPE_CHECKING:
    from . import OpenThermGatewayHub


def _get_gateway(call: ServiceCall) -> OpenThermGatewayHub:
    gw_id: str = call.data[ATTR_GW_ID]
    gw_hub: OpenThermGatewayHub | None = (
        call.hass.data.get(DATA_OPENTHERM_GW, {}).get(DATA_GATEWAYS, {}).get(gw_id)
    )
    if gw_hub is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_gateway_id",
            translation_placeholders={"gw_id": gw_id},
        )
    return gw_hub


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the component."""
    service_reset_schema = vol.Schema({vol.Required(ATTR_GW_ID): vol.All(cv.string)})
    service_set_central_heating_ovrd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_CH_OVRD): cv.boolean,
        }
    )
    service_set_clock_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Optional(ATTR_DATE, default=date.today): cv.date,
            vol.Optional(ATTR_TIME, default=lambda: datetime.now().time()): cv.time,
        }
    )
    service_set_control_setpoint_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=90)
            ),
        }
    )
    service_set_hot_water_setpoint_schema = service_set_control_setpoint_schema
    service_set_hot_water_ovrd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_DHW_OVRD): vol.Any(
                vol.Equal("A"), vol.All(vol.Coerce(int), vol.Range(min=0, max=1))
            ),
        }
    )
    service_set_gpio_mode_schema = vol.Schema(
        vol.Any(
            vol.Schema(
                {
                    vol.Required(ATTR_GW_ID): vol.All(cv.string),
                    vol.Required(ATTR_ID): vol.Equal("A"),
                    vol.Required(ATTR_MODE): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=6)
                    ),
                }
            ),
            vol.Schema(
                {
                    vol.Required(ATTR_GW_ID): vol.All(cv.string),
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
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_ID): vol.In("ABCDEF"),
            vol.Required(ATTR_MODE): vol.In("RXTBOFHWCEMP"),
        }
    )
    service_set_max_mod_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_LEVEL): vol.All(
                vol.Coerce(int), vol.Range(min=-1, max=100)
            ),
        }
    )
    service_set_oat_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=-40, max=99)
            ),
        }
    )
    service_set_sb_temp_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=30)
            ),
        }
    )
    service_send_transp_cmd_schema = vol.Schema(
        {
            vol.Required(ATTR_GW_ID): vol.All(cv.string),
            vol.Required(ATTR_TRANSP_CMD): vol.All(
                cv.string, vol.Length(min=2, max=2), vol.Coerce(str.upper)
            ),
            vol.Required(ATTR_TRANSP_ARG): vol.All(
                cv.string, vol.Length(min=1, max=12)
            ),
        }
    )

    async def reset_gateway(call: ServiceCall) -> None:
        """Reset the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        mode_rst = gw_vars.OTGW_MODE_RESET
        await gw_hub.gateway.set_mode(mode_rst)

    hass.services.async_register(
        DOMAIN, SERVICE_RESET_GATEWAY, reset_gateway, service_reset_schema
    )

    async def set_ch_ovrd(call: ServiceCall) -> None:
        """Set the central heating override on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_ch_enable_bit(1 if call.data[ATTR_CH_OVRD] else 0)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CH_OVRD,
        set_ch_ovrd,
        service_set_central_heating_ovrd_schema,
    )

    async def set_control_setpoint(call: ServiceCall) -> None:
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_control_setpoint(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CONTROL_SETPOINT,
        set_control_setpoint,
        service_set_control_setpoint_schema,
    )

    async def set_dhw_ovrd(call: ServiceCall) -> None:
        """Set the domestic hot water override on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_hot_water_ovrd(call.data[ATTR_DHW_OVRD])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_OVRD,
        set_dhw_ovrd,
        service_set_hot_water_ovrd_schema,
    )

    async def set_dhw_setpoint(call: ServiceCall) -> None:
        """Set the domestic hot water setpoint on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_dhw_setpoint(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SETPOINT,
        set_dhw_setpoint,
        service_set_hot_water_setpoint_schema,
    )

    async def set_device_clock(call: ServiceCall) -> None:
        """Set the clock on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        attr_date = call.data[ATTR_DATE]
        attr_time = call.data[ATTR_TIME]
        await gw_hub.gateway.set_clock(datetime.combine(attr_date, attr_time))

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CLOCK, set_device_clock, service_set_clock_schema
    )

    async def set_gpio_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway GPIO modes."""
        gw_hub = _get_gateway(call)
        gpio_id = call.data[ATTR_ID]
        gpio_mode = call.data[ATTR_MODE]
        await gw_hub.gateway.set_gpio_mode(gpio_id, gpio_mode)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_GPIO_MODE, set_gpio_mode, service_set_gpio_mode_schema
    )

    async def set_led_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway LED modes."""
        gw_hub = _get_gateway(call)
        led_id = call.data[ATTR_ID]
        led_mode = call.data[ATTR_MODE]
        await gw_hub.gateway.set_led_mode(led_id, led_mode)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_LED_MODE, set_led_mode, service_set_led_mode_schema
    )

    async def set_max_mod(call: ServiceCall) -> None:
        """Set the max modulation level."""
        gw_hub = _get_gateway(call)
        level = call.data[ATTR_LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = "-"
        await gw_hub.gateway.set_max_relative_mod(level)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_MAX_MOD, set_max_mod, service_set_max_mod_schema
    )

    async def set_outside_temp(call: ServiceCall) -> None:
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_outside_temp(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_OAT, set_outside_temp, service_set_oat_schema
    )

    async def set_setback_temp(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_setback_temp(call.data[ATTR_TEMPERATURE])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SB_TEMP, set_setback_temp, service_set_sb_temp_schema
    )

    async def send_transparent_cmd(call: ServiceCall) -> None:
        """Send a transparent OpenTherm Gateway command."""
        gw_hub = _get_gateway(call)
        transp_cmd = call.data[ATTR_TRANSP_CMD]
        transp_arg = call.data[ATTR_TRANSP_ARG]
        await gw_hub.gateway.send_transparent_command(transp_cmd, transp_arg)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TRANSP_CMD,
        send_transparent_cmd,
        service_send_transp_cmd_schema,
    )
