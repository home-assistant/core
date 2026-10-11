"""Config flow for the HP Printer integration."""

from typing import Any, override

from aiohpprinter import HpPrinter, HpPrinterError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
    }
)


class HpPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HP Printer."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = HpPrinter(
                user_input[CONF_HOST], async_get_clientsession(self.hass)
            )
            try:
                device = await client.device()
                # Updates fail without the status endpoint, so check it too.
                await client.status()
            except HpPrinterError:
                errors["base"] = "cannot_connect"
            else:
                if not device.serial_number:
                    return self.async_abort(reason="missing_serial_number")
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.make_and_model or user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
