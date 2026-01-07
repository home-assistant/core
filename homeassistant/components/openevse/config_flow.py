"""Config flow for OpenEVSE integration."""

from typing import Any

from openevsehttp.__main__ import OpenEVSE
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN


class OpenEVSEConfigFlow(ConfigFlow, domain=DOMAIN):
    """OpenEVSE config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def check_status(self, host: str) -> bool:
        """Check if we can connect to the OpenEVSE charger."""

        charger = OpenEVSE(host)
        try:
            await charger.test_and_get()
        except TimeoutError:
            return False
        else:
            return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = None
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            if await self.check_status(user_input[CONF_HOST]):
                return self.async_create_entry(
                    title=f"OpenEVSE {user_input[CONF_HOST]}",
                    data=user_input,
                )
            errors = {CONF_HOST: "cannot_connect"}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_import(self, data: dict[str, str]) -> ConfigFlowResult:
        """Handle the initial step."""

        self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})

        if not await self.check_status(data[CONF_HOST]):
            return self.async_abort(reason="unavailable_host")

        return self.async_create_entry(
            title=f"OpenEVSE {data[CONF_HOST]}",
            data=data,
        )
