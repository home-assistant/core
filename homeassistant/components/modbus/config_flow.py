"""Config flow to allow modbus create a config_entry."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import MODBUS_DOMAIN, MODBUS_UIID


class ModbusConfigFlow(ConfigFlow, domain=MODBUS_DOMAIN):
    """mondbus integration config flow."""

    VERSION = 1
    MINOR_VERION = 0

    def __init__(self) -> None:
        """Set up flow instance."""

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure a flow initialized by the user."""
        return self.async_abort(reason="no_online_reconfig")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="no_online_config")

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        await self.async_set_unique_id(MODBUS_UIID)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=MODBUS_DOMAIN + "_integration",
            data=import_data,
        )
