"""Config flow for Discovergy integration."""
from __future__ import annotations

import logging
from typing import Any

import pydiscovergy
import pydiscovergy.error as discovergyError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    APP_NAME,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from schema with values provided by the user.
    """
    try:
        discovergy_instance = pydiscovergy.Discovergy(APP_NAME)
        (access_token, consumer_token) = await discovergy_instance.login(
            data[CONF_EMAIL], data[CONF_PASSWORD]
        )

        # store token pairs for later use so we don't need to request new pairs each time
        data[CONF_CONSUMER_KEY] = consumer_token.key
        data[CONF_CONSUMER_SECRET] = consumer_token.secret
        data[CONF_ACCESS_TOKEN] = access_token.token
        data[CONF_ACCESS_TOKEN_SECRET] = access_token.token_secret
    except discovergyError.InvalidLogin as err:
        raise InvalidAuth from err
    except discovergyError.HTTPError as err:
        raise CannotConnect(f"Error while communicating with API: {err}") from err

    return {"title": data[CONF_EMAIL], "data": data}


def make_schema(user_input: dict[str, Any] = None, step_id: str = "user") -> vol.Schema:
    """Return the schema filled with user_input defaults."""
    if step_id == "reauth_confirm":
        return vol.Schema(
            {
                vol.Required(
                    CONF_PASSWORD,
                    default=(
                        user_input[CONF_PASSWORD]
                        if user_input is not None and CONF_PASSWORD in user_input
                        else ""
                    ),
                ): str,
            }
        )

    return vol.Schema(
        {
            vol.Required(
                CONF_EMAIL,
                default=(
                    user_input[CONF_EMAIL]
                    if user_input is not None and CONF_EMAIL in user_input
                    else ""
                ),
            ): str,
            vol.Required(
                CONF_PASSWORD,
                default=(
                    user_input[CONF_PASSWORD]
                    if user_input is not None and CONF_PASSWORD in user_input
                    else ""
                ),
            ): str,
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discovergy."""

    VERSION = 1

    existing_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=make_schema(user_input),
            )

        return await self._validate_and_save(user_input)

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform re-auth upon an API authentication error."""
        # try to get new access token with existing credentials automatically
        if user_input:
            try:
                self.existing_entry = await self.async_set_unique_id(
                    self.context["unique_id"]
                )
                result = await validate_input(
                    self.hass,
                    {
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            except CannotConnect as err:
                _LOGGER.error("Error while re-authenticating: %s", err)
            except InvalidAuth:
                _LOGGER.debug(
                    "Invalid credentials supplied while automatic re-auth. Need manual re-auth"
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
            else:
                if self.existing_entry:
                    _LOGGER.debug("Automatic token renewal successful. Reloading entry")
                    return await self._async_create_or_update(
                        title=result["title"], data=result["data"]
                    )

        # otherwise do manual re-auth
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform manual re-auth when e.g. the password has change."""
        if self.existing_entry is None:
            return await self._validate_and_save(user_input)

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=make_schema(user_input, "reauth_confirm"),
                description_placeholders={
                    "email": self.existing_entry.data[CONF_EMAIL]
                },
            )

        user_input = {CONF_EMAIL: self.existing_entry.data[CONF_EMAIL], **user_input}
        return await self._validate_and_save(user_input, "reauth_confirm")

    async def _validate_and_save(
        self, user_input: dict[str, Any] | None = None, step_id: str = "user"
    ) -> FlowResult:
        """Validate user input and create/update config entry."""
        errors = {}

        if user_input:
            try:
                result = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._async_create_or_update(
                    title=result["title"], data=result["data"]
                )

        return self.async_show_form(
            step_id=step_id, data_schema=make_schema(user_input, step_id), errors=errors
        )

    async def _async_create_or_update(self, title: str, data: dict) -> FlowResult:
        """Update existing config entry after re-auth or create a new one."""
        if self.existing_entry:
            self.hass.config_entries.async_update_entry(self.existing_entry, data=data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        # set unique id to title which is the account email
        await self.async_set_unique_id(title.lower())
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data=data)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
