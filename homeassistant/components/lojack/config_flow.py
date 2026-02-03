"""Config flow for LoJack integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, MIN_POLL_INTERVAL, MAX_POLL_INTERVAL, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]

    from lojack_api import LoJackClient, AuthenticationError, ApiError

    try:
        # v0.5.0 API: create(username, password)
        client = await LoJackClient.create(username, password)
        try:
            devices = await client.list_devices()
            device_count = len(devices) if devices else 0
        finally:
            await client.close()

        return {"title": f"LoJack ({username})", "device_count": device_count}

    except AuthenticationError as err:
        raise InvalidAuth(f"Invalid username or password: {err}") from err
    except ApiError as err:
        raise CannotConnect(f"API error: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation")
        raise CannotConnect(str(err)) from err


class LoJackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LoJack."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if this account is already configured
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            try:
                user_input[CONF_USERNAME] = reauth_entry.data[CONF_USERNAME]
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, **user_input},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return LoJackOptionsFlowHandler(config_entry)


class LoJackOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for LoJack integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate done by voluptuous schema; simply create the entry
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL)

        schema = vol.Schema(
            {
                vol.Optional(
                    "poll_interval", default=current
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL))
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return LoJackOptionsFlowHandler(config_entry)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
