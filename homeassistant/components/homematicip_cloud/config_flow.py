"""Config flow to configure the HomematicIP Cloud component."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import _LOGGER, DOMAIN, HMIPC_AUTHTOKEN, HMIPC_HAPID, HMIPC_NAME, HMIPC_PIN
from .hap import HomematicipAuth


class HomematicipCloudFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the HomematicIP Cloud component."""

    VERSION = 1

    auth: HomematicipAuth

    def __init__(self) -> None:
        """Initialize HomematicIP Cloud config flow."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            user_input[HMIPC_HAPID] = user_input[HMIPC_HAPID].replace("-", "").upper()

            await self.async_set_unique_id(user_input[HMIPC_HAPID])
            self._abort_if_unique_id_configured()

            self.auth = HomematicipAuth(self.hass, user_input)
            connected = await self.auth.async_setup()
            if connected:
                _LOGGER.info("Connection to HomematicIP Cloud established")
                return await self.async_step_link()

            _LOGGER.info("Connection to HomematicIP Cloud failed")
            errors["base"] = "invalid_sgtin_or_pin"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(HMIPC_HAPID): str,
                    vol.Optional(HMIPC_NAME): str,
                    vol.Optional(HMIPC_PIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_link(self, user_input=None) -> FlowResult:
        """Attempt to link with the HomematicIP Cloud access point."""
        errors = {}

        pressed = await self.auth.async_checkbutton()
        if pressed:
            authtoken = await self.auth.async_register()
            if authtoken:
                _LOGGER.info("Write config entry for HomematicIP Cloud")
                return self.async_create_entry(
                    title=self.auth.config.get(HMIPC_HAPID),
                    data={
                        HMIPC_HAPID: self.auth.config.get(HMIPC_HAPID),
                        HMIPC_AUTHTOKEN: authtoken,
                        HMIPC_NAME: self.auth.config.get(HMIPC_NAME),
                    },
                )
            return self.async_abort(reason="connection_aborted")
        errors["base"] = "press_the_button"

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_import(self, import_info) -> FlowResult:
        """Import a new access point as a config entry."""
        hapid = import_info[HMIPC_HAPID].replace("-", "").upper()
        authtoken = import_info[HMIPC_AUTHTOKEN]
        name = import_info[HMIPC_NAME]

        await self.async_set_unique_id(hapid)
        self._abort_if_unique_id_configured()

        _LOGGER.info("Imported authentication for %s", hapid)
        return self.async_create_entry(
            title=hapid,
            data={HMIPC_AUTHTOKEN: authtoken, HMIPC_HAPID: hapid, HMIPC_NAME: name},
        )
