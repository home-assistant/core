"""Config flow for Litter-Robot integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pylitterbot import Account
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_REAUTH_RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class LitterRobotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Litter-Robot."""

    VERSION = 1
    MINOR_VERSION = 2

    username: str
    _account_user_id: str | None = None

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
        errors: dict[str, str] = {}
        if user_input:
            reauth_entry = self._get_reauth_entry()
            result, errors = await self._async_validate_and_update_entry(
                reauth_entry, user_input
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_RECONFIGURE_SCHEMA,
            description_placeholders={CONF_USERNAME: self.username},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow request."""
        reconfigure_entry = self._get_reconfigure_entry()
        self.username = reconfigure_entry.data[CONF_USERNAME]

        self._async_abort_entries_match({CONF_USERNAME: self.username})

        errors: dict[str, str] = {}
        if user_input:
            result, errors = await self._async_validate_and_update_entry(
                reconfigure_entry, user_input
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_REAUTH_RECONFIGURE_SCHEMA,
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
                await self.async_set_unique_id(self._account_user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _async_validate_and_update_entry(
        self, entry: ConfigEntry, user_input: dict[str, Any]
    ) -> tuple[ConfigFlowResult | None, dict[str, str]]:
        """Validate credentials and update an existing entry if valid."""
        errors: dict[str, str] = {}
        full_input: dict[str, Any] = user_input | {CONF_USERNAME: self.username}
        if not (error := await self._async_validate_input(full_input)):
            await self.async_set_unique_id(self._account_user_id)
            self._abort_if_unique_id_mismatch()
            return (
                self.async_update_reload_and_abort(
                    entry,
                    data_updates=full_input,
                ),
                errors,
            )
        errors["base"] = error
        return None, errors

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
        self._account_user_id = account.user_id
        if not self._account_user_id:
            return "unknown"
        return ""
