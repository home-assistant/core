"""Config flow for Litter-Robot integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pylitterbot import Account
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class LitterRobotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Litter-Robot."""

    VERSION = 1

    username: str

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        self.username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle user's reauth credentials."""
        errors = {}
        if user_input:
            user_input = user_input | {CONF_USERNAME: self.username}
            if not (error := await self._async_validate_input(user_input)):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_USERNAME: self.username},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            if not (error := await self._async_validate_input(user_input)):
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _async_validate_input(self, user_input: Mapping[str, Any]) -> str:
        """Validate login credentials."""
        account = Account(websession=async_get_clientsession(self.hass))
        try:
            await account.connect(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            await account.disconnect()
        except LitterRobotLoginException:
            return "invalid_auth"
        except LitterRobotException:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return ""
