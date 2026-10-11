"""Config flow for SwitchBot via API integration."""

from collections.abc import Mapping
from logging import getLogger
from typing import Any, override

import probatio
from switchbot_api import (
    SwitchBotAPI,
    SwitchBotAuthenticationError,
    SwitchBotConnectionError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN

from .const import DOMAIN, ENTRY_TITLE

_LOGGER = getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_TOKEN)): str,
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
    }
)


class SwitchBotCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot via API."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await SwitchBotAPI(
                    token=user_input[CONF_API_TOKEN], secret=user_input[CONF_API_KEY]
                ).list_devices()
            except SwitchBotConnectionError:
                errors["base"] = "cannot_connect"
            except SwitchBotAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_API_TOKEN], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new token and secret."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await SwitchBotAPI(
                    token=user_input[CONF_API_TOKEN], secret=user_input[CONF_API_KEY]
                ).list_devices()
            except SwitchBotConnectionError:
                errors["base"] = "cannot_connect"
            except SwitchBotAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                reauth_entry = self._get_reauth_entry()
                existing_entry = (
                    self.hass.config_entries.async_entry_for_domain_unique_id(
                        DOMAIN, user_input[CONF_API_TOKEN]
                    )
                )
                if existing_entry and existing_entry.entry_id != reauth_entry.entry_id:
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    reauth_entry, unique_id=user_input[CONF_API_TOKEN], data=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
