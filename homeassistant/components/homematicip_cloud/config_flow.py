"""Config flow to configure the HomematicIP Cloud component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import _LOGGER, DOMAIN, HMIPC_AUTHTOKEN, HMIPC_HAPID, HMIPC_NAME, HMIPC_PIN
from .hap import HomematicipAuth


class HomematicipCloudFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for the HomematicIP Cloud component."""

    VERSION = 1

    auth: HomematicipAuth

    def __init__(self) -> None:
        """Initialize HomematicIP Cloud config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            user_input[HMIPC_HAPID] = user_input[HMIPC_HAPID].replace("-", "").upper()

            await self.async_set_unique_id(user_input[HMIPC_HAPID])
            self._abort_if_unique_id_configured()

            self.auth = HomematicipAuth(self.hass, user_input)
            connected = await self.auth.async_setup()
            if connected:
                _LOGGER.debug("Connection to HomematicIP Cloud established")
                return await self.async_step_link()

            _LOGGER.debug("Connection to HomematicIP Cloud failed")
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

    async def async_step_link(self, user_input: None = None) -> ConfigFlowResult:
        """Attempt to link with the HomematicIP Cloud access point."""
        errors = {}

        pressed = await self.auth.async_checkbutton()
        if pressed:
            authtoken = await self.auth.async_register()
            if authtoken:
                _LOGGER.debug("Write config entry for HomematicIP Cloud")
                if self.source == "reauth":
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={HMIPC_AUTHTOKEN: authtoken},
                    )
                return self.async_create_entry(
                    title=self.auth.config[HMIPC_HAPID],
                    data={
                        HMIPC_HAPID: self.auth.config[HMIPC_HAPID],
                        HMIPC_AUTHTOKEN: authtoken,
                        HMIPC_NAME: self.auth.config.get(HMIPC_NAME),
                    },
                )
            if self.source == "reauth":
                errors["base"] = "connection_aborted"
            else:
                return self.async_abort(reason="connection_aborted")
        else:
            errors["base"] = "press_the_button"

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the auth token becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation and start link process."""
        errors = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            config = {
                HMIPC_HAPID: reauth_entry.data[HMIPC_HAPID],
                HMIPC_PIN: user_input.get(HMIPC_PIN),
                HMIPC_NAME: reauth_entry.data.get(HMIPC_NAME),
            }
            self.auth = HomematicipAuth(self.hass, config)
            connected = await self.auth.async_setup()
            if connected:
                return await self.async_step_link()
            errors["base"] = "invalid_sgtin_or_pin"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(HMIPC_PIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, str]) -> ConfigFlowResult:
        """Import a new access point as a config entry."""
        hapid = import_data[HMIPC_HAPID].replace("-", "").upper()
        authtoken = import_data[HMIPC_AUTHTOKEN]
        name = import_data[HMIPC_NAME]

        await self.async_set_unique_id(hapid)
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Imported authentication for %s", hapid)
        return self.async_create_entry(
            title=hapid,
            data={HMIPC_AUTHTOKEN: authtoken, HMIPC_HAPID: hapid, HMIPC_NAME: name},
        )
