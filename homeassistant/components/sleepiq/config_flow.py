"""Config flow to configure SleepIQ component."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from asyncsleepiq import AsyncSleepIQ, SleepIQLoginException, SleepIQTimeoutException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SleepIQFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a SleepIQ config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a SleepIQ account as a config entry.

        This flow is triggered by 'async_setup' for configured accounts.
        """
        await self.async_set_unique_id(import_data[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        if error := await try_connection(self.hass, import_data):
            _LOGGER.error("Could not authenticate with SleepIQ server: %s", error)
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=import_data[CONF_USERNAME], data=import_data
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Don't allow multiple instances with the same username
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            if error := await try_connection(self.hass, user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            last_step=True,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None
        if user_input is not None:
            data = {
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            if not (error := await try_connection(self.hass, data)):
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=data
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME],
            },
        )


async def try_connection(hass: HomeAssistant, user_input: dict[str, Any]) -> str | None:
    """Test if the given credentials can successfully login to SleepIQ."""

    client_session = async_get_clientsession(hass)

    gateway = AsyncSleepIQ(client_session=client_session)
    try:
        await gateway.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
    except SleepIQLoginException:
        return "invalid_auth"
    except SleepIQTimeoutException:
        return "cannot_connect"

    return None
