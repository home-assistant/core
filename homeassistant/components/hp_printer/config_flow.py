"""Config flow for the HP Printer integration."""

from typing import Any, override

from aiohpprinter import HpPrinter, HpPrinterError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import DOMAIN, SECTION_ADVANCED_SETTINGS

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(SECTION_ADVANCED_SETTINGS): section(
            probatio.Schema(
                {
                    probatio.Required(CONF_SSL, default=False): BooleanSelector(),
                    probatio.Optional(CONF_PORT): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            {"collapsed": True},
        ),
    }
)


class HpPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HP Printer."""

    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST],
                **user_input[SECTION_ADVANCED_SETTINGS],
            }
            if CONF_PORT in data:
                data[CONF_PORT] = int(data[CONF_PORT])
            client = HpPrinter(
                data[CONF_HOST],
                async_get_clientsession(self.hass),
                port=data.get(CONF_PORT),
                ssl=data[CONF_SSL],
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
                    title=device.make_and_model or data[CONF_HOST],
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
