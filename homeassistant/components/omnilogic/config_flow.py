"""Config flow for Omnilogic integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from omnilogic import LoginException, OmniLogic, OmniLogicException
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DEFAULT_PH_OFFSET, DOMAIN
from .coordinator import OmniLogicConfigEntry

_LOGGER = logging.getLogger(__name__)


class OmniLogicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Omnilogic."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: OmniLogicConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            session = aiohttp_client.async_get_clientsession(self.hass)
            omni = OmniLogic(username, password, session)

            try:
                await omni.connect()
            except LoginException:
                errors["base"] = "invalid_auth"
            except OmniLogicException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input["username"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Omnilogic", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_USERNAME): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            omni = OmniLogic(
                reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )

            try:
                await omni.connect()
            except LoginException:
                errors["base"] = "invalid_auth"
            except OmniLogicException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )


class OptionsFlowHandler(OptionsFlow):
    """Handle Omnilogic client options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        "ph_offset",
                        default=self.config_entry.options.get(
                            "ph_offset", DEFAULT_PH_OFFSET
                        ),
                    ): probatio.All(probatio.Coerce(float)),
                }
            ),
        )
