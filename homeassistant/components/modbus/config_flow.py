"""Config flow to allow modbus create a config_entry."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import _LOGGER, MODBUS_DOMAIN


class ModbusConfigFlow(ConfigFlow, domain=MODBUS_DOMAIN):
    """mondbus integration config flow."""

    VERSION = 1
    MINOR_VERION = 1

    def __init__(self) -> None:
        """Initialize flow."""

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure a flow initialized by the user."""
        _LOGGER.debug(f"modbus_cf async_step_reconfigure called <<{user_input}>>")
        return await self.async_step_user(user_input=user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _LOGGER.debug(f"modbus_cf async_step_user called <<{user_input}>>")
        if user_input is not None:
            return self.async_create_entry(
                title=MODBUS_DOMAIN + "_integration",
                data=user_input,
            )
        return self.async_show_form(step_id="user")

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        _LOGGER.debug(f"modbus_cf async_step_import called <<{import_data}>>")
        return await self.async_step_user(import_data)
