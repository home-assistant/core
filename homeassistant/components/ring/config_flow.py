"""Config flow for Ring integration."""

from collections.abc import Mapping
import logging
from typing import Any

from ring_doorbell import Auth, AuthenticationError, Requires2FAError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import get_auth_agent_id
from .const import CONF_2FA, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    user_agent, hardware_id = await get_auth_agent_id(hass)
    auth = Auth(
        user_agent,
        http_client_session=async_get_clientsession(hass),
        hardware_id=hardware_id,
    )

    try:
        token = await auth.async_fetch_token(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_2FA),
        )
    except Requires2FAError as err:
        raise Require2FA from err
    except AuthenticationError as err:
        raise InvalidAuth from err

    return token


class RingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring."""

    VERSION = 1

    user_pass: dict[str, Any] = {}
    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            try:
                token = await validate_input(self.hass, user_input)
            except Require2FA:
                self.user_pass = user_input

                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={CONF_USERNAME: user_input[CONF_USERNAME], CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
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
            except Exception:
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


class Require2FA(HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
