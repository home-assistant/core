"""Support for OpenTherm Gateway devices."""

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import probatio
import pyotgw.vars as gw_vars

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
import homeassistant.util.dt as dt_util

from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW, DOMAIN


class OpenThermGwService(StrEnum):
    """Store keys for OpenTherm Gateway services."""

    RESET_GATEWAY = "reset_gateway"
    SET_CENTRAL_HEATING_OVRD = "set_central_heating_ovrd"
    SET_CLOCK = "set_clock"
    SET_CONTROL_SETPOINT = "set_control_setpoint"
    SET_HOT_WATER_OVRD = "set_hot_water_ovrd"
    SET_HOT_WATER_SETPOINT = "set_hot_water_setpoint"
    SET_GPIO_MODE = "set_gpio_mode"
    SET_LED_MODE = "set_led_mode"
    SET_MAX_MODULATION = "set_max_modulation"
    SET_OUTSIDE_TEMPERATURE = "set_outside_temperature"
    SET_SETBACK_TEMPERATURE = "set_setback_temperature"
    SEND_TRANSPARENT_COMMAND = "send_transparent_command"


class OpenThermGwServiceArgument(StrEnum):
    """Store keys for OpenTherm Gateway service arguments."""

    GATEWAY_ID = "gateway_id"
    CH_OVERRIDE = "ch_override"
    DATE = "date"
    TIME = "time"
    TEMPERATURE = "temperature"
    DHW_OVERRIDE = "dhw_override"
    ID = "id"
    MODE = "mode"
    LEVEL = "level"
    TRANSP_CMD = "transp_cmd"
    TRANSP_ARG = "transp_arg"


if TYPE_CHECKING:
    from . import OpenThermGatewayHub


def _get_gateway(call: ServiceCall) -> OpenThermGatewayHub:
    gw_id: str = call.data[OpenThermGwServiceArgument.GATEWAY_ID]
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
    service_reset_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            )
        }
    )
    service_set_central_heating_ovrd_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.CH_OVERRIDE): cv.boolean,
        }
    )
    service_set_clock_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Optional(
                OpenThermGwServiceArgument.DATE, default=date.today
            ): cv.date,
            probatio.Optional(
                OpenThermGwServiceArgument.TIME,
                default=lambda: dt_util.naive_now().time(),
            ): cv.time,
        }
    )
    service_set_control_setpoint_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.TEMPERATURE): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0, max=90)
            ),
        }
    )
    service_set_hot_water_setpoint_schema = service_set_control_setpoint_schema
    service_set_hot_water_ovrd_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.DHW_OVERRIDE): probatio.Any(
                probatio.Equal("A"),
                probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=1)),
            ),
        }
    )
    service_set_gpio_mode_schema = probatio.Schema(
        probatio.TaggedUnion(
            OpenThermGwServiceArgument.ID,
            [
                probatio.Schema(
                    {
                        probatio.Required(
                            OpenThermGwServiceArgument.GATEWAY_ID
                        ): probatio.All(cv.string),
                        probatio.Required(OpenThermGwServiceArgument.ID): "A",
                        probatio.Required(
                            OpenThermGwServiceArgument.MODE
                        ): probatio.All(
                            probatio.Coerce(int), probatio.Range(min=0, max=6)
                        ),
                    }
                ),
                probatio.Schema(
                    {
                        probatio.Required(
                            OpenThermGwServiceArgument.GATEWAY_ID
                        ): probatio.All(cv.string),
                        probatio.Required(OpenThermGwServiceArgument.ID): "B",
                        probatio.Required(
                            OpenThermGwServiceArgument.MODE
                        ): probatio.All(
                            probatio.Coerce(int), probatio.Range(min=0, max=7)
                        ),
                    }
                ),
            ],
        )
    )
    service_set_led_mode_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.ID): probatio.In("ABCDEF"),
            probatio.Required(OpenThermGwServiceArgument.MODE): probatio.In(
                "RXTBOFHWCEMP"
            ),
        }
    )
    service_set_max_mod_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.LEVEL): probatio.All(
                probatio.Coerce(int), probatio.Range(min=-1, max=100)
            ),
        }
    )
    service_set_oat_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.TEMPERATURE): probatio.All(
                probatio.Coerce(float), probatio.Range(min=-40, max=99)
            ),
        }
    )
    service_set_sb_temp_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.TEMPERATURE): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0, max=30)
            ),
        }
    )
    service_send_transp_cmd_schema = probatio.Schema(
        {
            probatio.Required(OpenThermGwServiceArgument.GATEWAY_ID): probatio.All(
                cv.string
            ),
            probatio.Required(OpenThermGwServiceArgument.TRANSP_CMD): probatio.All(
                cv.string, probatio.Length(min=2, max=2), probatio.Coerce(str.upper)
            ),
            probatio.Required(OpenThermGwServiceArgument.TRANSP_ARG): probatio.All(
                cv.string, probatio.Length(min=1, max=12)
            ),
        }
    )

    async def reset_gateway(call: ServiceCall) -> None:
        """Reset the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        mode_rst = gw_vars.OTGW_MODE_RESET
        await gw_hub.gateway.set_mode(mode_rst)

    hass.services.async_register(
        DOMAIN, OpenThermGwService.RESET_GATEWAY, reset_gateway, service_reset_schema
    )

    async def set_ch_ovrd(call: ServiceCall) -> None:
        """Set the central heating override on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_ch_enable_bit(
            1 if call.data[OpenThermGwServiceArgument.CH_OVERRIDE] else 0
        )

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_CENTRAL_HEATING_OVRD,
        set_ch_ovrd,
        service_set_central_heating_ovrd_schema,
    )

    async def set_control_setpoint(call: ServiceCall) -> None:
        """Set the control setpoint on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_control_setpoint(
            call.data[OpenThermGwServiceArgument.TEMPERATURE]
        )

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_CONTROL_SETPOINT,
        set_control_setpoint,
        service_set_control_setpoint_schema,
    )

    async def set_dhw_ovrd(call: ServiceCall) -> None:
        """Set the domestic hot water override on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_hot_water_ovrd(
            call.data[OpenThermGwServiceArgument.DHW_OVERRIDE]
        )

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_HOT_WATER_OVRD,
        set_dhw_ovrd,
        service_set_hot_water_ovrd_schema,
    )

    async def set_dhw_setpoint(call: ServiceCall) -> None:
        """Set the domestic hot water setpoint on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_dhw_setpoint(
            call.data[OpenThermGwServiceArgument.TEMPERATURE]
        )

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_HOT_WATER_SETPOINT,
        set_dhw_setpoint,
        service_set_hot_water_setpoint_schema,
    )

    async def set_device_clock(call: ServiceCall) -> None:
        """Set the clock on the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        attr_date = call.data[OpenThermGwServiceArgument.DATE]
        attr_time = call.data[OpenThermGwServiceArgument.TIME]
        await gw_hub.gateway.set_clock(datetime.combine(attr_date, attr_time))

    hass.services.async_register(
        DOMAIN, OpenThermGwService.SET_CLOCK, set_device_clock, service_set_clock_schema
    )

    async def set_gpio_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway GPIO modes."""
        gw_hub = _get_gateway(call)
        gpio_id = call.data[OpenThermGwServiceArgument.ID]
        gpio_mode = call.data[OpenThermGwServiceArgument.MODE]
        await gw_hub.gateway.set_gpio_mode(gpio_id, gpio_mode)

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_GPIO_MODE,
        set_gpio_mode,
        service_set_gpio_mode_schema,
        description_placeholders={
            "gpio_modes_documentation_url": "https://www.home-assistant.io/integrations/opentherm_gw/#gpio-modes"
        },
    )

    async def set_led_mode(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway LED modes."""
        gw_hub = _get_gateway(call)
        led_id = call.data[OpenThermGwServiceArgument.ID]
        led_mode = call.data[OpenThermGwServiceArgument.MODE]
        await gw_hub.gateway.set_led_mode(led_id, led_mode)

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_LED_MODE,
        set_led_mode,
        service_set_led_mode_schema,
        description_placeholders={
            "led_modes_documentation_url": "https://www.home-assistant.io/integrations/opentherm_gw/#led-modes"
        },
    )

    async def set_max_mod(call: ServiceCall) -> None:
        """Set the max modulation level."""
        gw_hub = _get_gateway(call)
        level = call.data[OpenThermGwServiceArgument.LEVEL]
        if level == -1:
            # Backend only clears setting on non-numeric values.
            level = "-"
        await gw_hub.gateway.set_max_relative_mod(level)

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_MAX_MODULATION,
        set_max_mod,
        service_set_max_mod_schema,
    )

    async def set_outside_temp(call: ServiceCall) -> None:
        """Provide the outside temperature to the OpenTherm Gateway."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_outside_temp(
            call.data[OpenThermGwServiceArgument.TEMPERATURE]
        )

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_OUTSIDE_TEMPERATURE,
        set_outside_temp,
        service_set_oat_schema,
    )

    async def set_setback_temp(call: ServiceCall) -> None:
        """Set the OpenTherm Gateway SetBack temperature."""
        gw_hub = _get_gateway(call)
        await gw_hub.gateway.set_setback_temp(
            call.data[OpenThermGwServiceArgument.TEMPERATURE]
        )

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SET_SETBACK_TEMPERATURE,
        set_setback_temp,
        service_set_sb_temp_schema,
    )

    async def send_transparent_cmd(call: ServiceCall) -> None:
        """Send a transparent OpenTherm Gateway command."""
        gw_hub = _get_gateway(call)
        transp_cmd = call.data[OpenThermGwServiceArgument.TRANSP_CMD]
        transp_arg = call.data[OpenThermGwServiceArgument.TRANSP_ARG]
        await gw_hub.gateway.send_transparent_command(transp_cmd, transp_arg)

    hass.services.async_register(
        DOMAIN,
        OpenThermGwService.SEND_TRANSPARENT_COMMAND,
        send_transparent_cmd,
        service_send_transp_cmd_schema,
        description_placeholders={
            "opentherm_gateway_firmware_url": "https://otgw.tclcode.com/firmware.html"
        },
    )
