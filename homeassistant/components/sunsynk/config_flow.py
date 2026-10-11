"""Config flow for the Sunsynk integration."""

from typing import Any, override

from modbus_connection import ModbusError, ModbusTcpParams
import probatio
from sunsynk.client import SunsynkClient
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from sunsynk_modbus import SunsynkInverter

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    LOGGER,
    TYPE_CLOUD,
    TYPE_MODBUS,
)

STEP_CLOUD_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)

STEP_MODBUS_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            probatio.Coerce(int),
        ),
    }
)


class SunsynkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunsynk."""

    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select how to connect to the inverter."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_CLOUD, TYPE_MODBUS]
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a Sunsynk Connect account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SunsynkClient(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                user = await client.get_user()
            except SunsynkAuthenticationError:
                errors["base"] = "invalid_auth"
            except SunsynkConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={CONF_TYPE: TYPE_CLOUD, **user_input},
                )

        return self.async_show_form(
            step_id=TYPE_CLOUD,
            data_schema=self.add_suggested_values_to_schema(
                STEP_CLOUD_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an inverter that uses Modbus TCP."""
        errors: dict[str, str] = {}
        if user_input is not None:
            params = ModbusTcpParams(
                host=user_input[CONF_HOST], port=user_input[CONF_PORT]
            )
            try:
                async with async_get_temporary_unit(
                    self.hass, params, user_input[CONF_UNIT_ID]
                ) as unit:
                    inverter = SunsynkInverter(unit)
                    await inverter.async_ensure_setup()
            except (ModbusError, HomeAssistantError) as err:
                LOGGER.debug("Cannot read the inverter over Modbus: %s", err)
                errors["base"] = "cannot_connect"
            else:
                serial_number = inverter.identity.serial_number
                if not serial_number:
                    return self.async_abort(reason="no_serial_number")
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(error="already_configured_device")
                return self.async_create_entry(
                    title=f"Inverter {serial_number}",
                    data={CONF_TYPE: TYPE_MODBUS, **user_input},
                )

        return self.async_show_form(
            step_id=TYPE_MODBUS,
            data_schema=self.add_suggested_values_to_schema(
                STEP_MODBUS_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
