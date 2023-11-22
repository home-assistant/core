"""Config flow for Ring integration."""
from collections.abc import Mapping
import logging
from typing import Any

import ring_doorbell
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    APPLICATION_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    __version__ as ha_version,
)
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_2FA, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    auth = ring_doorbell.Auth(f"{APPLICATION_NAME}/{ha_version}")

    try:
        token = await hass.async_add_executor_job(
            auth.fetch_token,
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_2FA),
        )
    except ring_doorbell.Requires2FAError as err:
        raise Require2FA from err
    except ring_doorbell.AuthenticationError as err:
        raise InvalidAuth from err

    return token


class RingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring."""

    VERSION = 1

    user_pass: dict[str, Any] = {}
    reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                token = await validate_input(self.hass, user_input)
            except Require2FA:
                self.user_pass = user_input

                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={CONF_USERNAME: user_input[CONF_USERNAME], CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2fa step."""
        if user_input:
            if self.reauth_entry:
                return await self.async_step_reauth_confirm(
                    {**self.user_pass, **user_input}
                )

            return await self.async_step_user({**self.user_pass, **user_input})

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema({vol.Required(CONF_2FA): str}),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        assert self.reauth_entry is not None

        if user_input:
            user_input[CONF_USERNAME] = self.reauth_entry.data[CONF_USERNAME]
            try:
                token = await validate_input(self.hass, user_input)
            except Require2FA:
                self.user_pass = user_input
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_TOKEN: token,
                }
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=data
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                CONF_USERNAME: self.reauth_entry.data[CONF_USERNAME]
            },
        )


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
