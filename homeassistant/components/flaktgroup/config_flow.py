"""Config flow to configure Flaktgroup devices."""

import logging
import math
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.util import slugify

from . import FlaktgroupModbusDataUpdateCoordinator
from .const import (
    CONF_MODBUS_COORDINATOR,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    HoldingRegisters,
)
from .modbus_coordinator import ModbusDatapoint

_LOGGER = logging.getLogger(__name__)


def _numeric_selector(min_value, max_value, unit_of_measurement, step: float = 1):
    if step < 1:
        coerce = vol.Coerce(float)
    else:
        coerce = vol.Coerce(int)
    return vol.All(
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=min_value,
                max=max_value,
                mode=selector.NumberSelectorMode.BOX,
                step=step,
                unit_of_measurement=unit_of_measurement,
            )
        ),
        coerce,
    )


def _temperature_selector(min_value, max_value):
    return _numeric_selector(min_value, max_value, "°C", 0.1)


class FlaktgroupConfigurationValue:
    """Class that represents Configuration value and it's validator."""

    def __init__(
        self, holding_register: HoldingRegisters, validator, scale: float = 1
    ) -> None:
        """Initialize the Fläktgroup Configuration Value."""
        self.name = slugify(holding_register.name)
        self.datapoint: ModbusDatapoint = holding_register.value
        self.validator = validator
        self.scale = scale


FAN_SPEED_OPTIONS = _numeric_selector(30, 100, "%")

SUPPLY_FAN_CONFIG = [
    FlaktgroupConfigurationValue(
        HoldingRegisters.SUPPLY_FAN_CONFIG_LOW, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.SUPPLY_FAN_CONFIG_NORMAL, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.SUPPLY_FAN_CONFIG_HIGH, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.SUPPLY_FAN_CONFIG_COOKER_HOOD, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.SUPPLY_FAN_CONFIG_FIREPLACE, FAN_SPEED_OPTIONS
    ),
]

EXTRACT_FAN_CONFIG = [
    FlaktgroupConfigurationValue(
        HoldingRegisters.EXTRACT_FAN_CONFIG_LOW, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.EXTRACT_FAN_CONFIG_NORMAL, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.EXTRACT_FAN_CONFIG_HIGH, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.EXTRACT_FAN_CONFIG_COOKER_HOOD, FAN_SPEED_OPTIONS
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.EXTRACT_FAN_CONFIG_FIREPLACE, FAN_SPEED_OPTIONS
    ),
]

TEMPERATURE_CONFIG = [
    FlaktgroupConfigurationValue(
        HoldingRegisters.TEMPERATURE_SET_POINT, _temperature_selector(7, 35), scale=0.1
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.MIN_SUPPLY_TEMPERATURE,
        _temperature_selector(15, 35),
        scale=0.1,
    ),
    FlaktgroupConfigurationValue(
        HoldingRegisters.MAX_SUPPLY_TEMPERATURE,
        _temperature_selector(15, 35),
        scale=0.1,
    ),
]

AIR_QUALITY_CONFIG = [
    FlaktgroupConfigurationValue(
        HoldingRegisters.SET_POINT_CO2, _numeric_selector(0, 2000, "ppm")
    )
]
MISC_CONFIG = [
    FlaktgroupConfigurationValue(
        HoldingRegisters.DIRTY_FILTER_ALARM_TIME, _numeric_selector(0, 600, "days")
    )
]


class FlaktgroupConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Flaktgroup device config flow."""

    def __init__(self):
        """Initialize the Flaktgroup config flow."""
        self.device_config = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return FlaktgroupOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a Flaktgroup config flow."""
        connected = False
        if user_input is not None:
            name = user_input[CONF_NAME]
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            update_interval = user_input[CONF_UPDATE_INTERVAL]

            try:
                client = ModbusTcpClient(host, port)
                connected = client.connect()
                client.close()
            except ModbusException as exception_error:
                connected = False
                _LOGGER.error(
                    "Cannot connect to %s at %s:%d. Exception: %s",
                    name,
                    host,
                    port,
                    str(exception_error),
                )

            if connected:
                await self.async_set_unique_id(f"{name}-{host}-{port}")

                self._abort_if_unique_id_configured(
                    updates={
                        CONF_NAME: name,
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_UPDATE_INTERVAL: update_interval,
                    }
                )

                self.device_config = {
                    CONF_NAME: name,
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_UPDATE_INTERVAL: update_interval,
                }

                return await self._create_entry(name)

        data = {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=8899): cv.port,
            vol.Required(CONF_UPDATE_INTERVAL, default=15): _numeric_selector(
                1, 9999, "s"
            ),
        }
        errors = {}
        if not connected:
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            description_placeholders=self.device_config,
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def _create_entry(self, server_name):
        """Create entry for device."""
        return self.async_create_entry(title=server_name, data=self.device_config)


def _find_parameter_config(form_config, name):
    for parameter_config in form_config:
        if parameter_config.name == name:
            return parameter_config
    raise NotImplementedError(f"Cannot find parameter {name} in form")


class FlaktgroupOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Fläktgroup options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the configuration menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "extract_fan",
                "supply_fan",
                "temperature",
                "air_quality",
                "misc",
            ],
        )

    async def async_step_extract_fan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the flow to configure Exhaust Fan."""
        return await self._async_show_config_form(
            "extract_fan", EXTRACT_FAN_CONFIG, user_input
        )

    async def async_step_supply_fan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the flow to configure Supply Fan."""
        return await self._async_show_config_form(
            "supply_fan", SUPPLY_FAN_CONFIG, user_input
        )

    async def async_step_temperature(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the flow to configure Temperature."""
        return await self._async_show_config_form(
            "temperature", TEMPERATURE_CONFIG, user_input
        )

    async def async_step_air_quality(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the flow to configure Air Quality."""
        return await self._async_show_config_form(
            "air_quality", AIR_QUALITY_CONFIG, user_input
        )

    async def async_step_misc(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the flow to configure Air Quality."""
        return await self._async_show_config_form("misc", MISC_CONFIG, user_input)

    def _number_to_scale(self, number, scale):
        actual_number = number * scale
        if scale < 1:
            decimals = round(math.log10(number))
            return round(actual_number, decimals)
        return round(actual_number)

    async def _async_show_config_form(
        self,
        form_name: str,
        form_config: list[FlaktgroupConfigurationValue],
        user_input: dict[str, Any] | None,
    ) -> FlowResult:
        modbus_coordinator: FlaktgroupModbusDataUpdateCoordinator = self.hass.data[
            DOMAIN
        ][self.config_entry.entry_id][CONF_MODBUS_COORDINATOR]
        values = {}
        description_placeholders = {}
        errors = {}

        for parameter_config in form_config:
            values[parameter_config.name] = self._number_to_scale(
                await modbus_coordinator.read_datapoint(parameter_config.datapoint),
                parameter_config.scale,
            )
            description_placeholders[parameter_config.name + "_result"] = ""

        if user_input:
            for name, new_value in user_input.items():
                if new_value == values[name]:
                    description_placeholders[name + "_result"] = "Not changed"
                else:
                    parameter_config = _find_parameter_config(form_config, name)
                    new_actual_value = self._number_to_scale(
                        new_value, 1 / parameter_config.scale
                    )
                    successful_write = await modbus_coordinator.write(
                        parameter_config.datapoint, new_actual_value
                    )

                    if successful_write:
                        description_placeholders[
                            f"{parameter_config.name}_result"
                        ] = f"Updated {str(values[parameter_config.name])} -> {str(new_value)}"
                    else:
                        errors[parameter_config.name] = "error_register_write"

                    values[parameter_config.name] = self._number_to_scale(
                        await modbus_coordinator.read_datapoint(
                            parameter_config.datapoint
                        ),
                        parameter_config.scale,
                    )

        options = {}
        for parameter_config in form_config:
            input_config = vol.Required(
                parameter_config.name, default=values[parameter_config.name]
            )
            options[input_config] = parameter_config.validator

        return self.async_show_form(
            step_id=form_name,
            data_schema=vol.Schema(options),
            description_placeholders=description_placeholders,
            errors=errors,
        )
