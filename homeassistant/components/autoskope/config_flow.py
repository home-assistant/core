"""Config flow for the Autoskope integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow as ConfigFlowBase,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_HOST, DOMAIN
from .models import AutoskopeApi, CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data.get(CONF_HOST, DEFAULT_HOST)
    api = AutoskopeApi(
        host=host,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        hass=hass,
    )
    error_to_raise: Exception | None = None

    try:
        # Use authenticate method which raises exceptions on failure
        await api.authenticate()
    except aiohttp.ClientError as err:
        _LOGGER.debug("Connection error during validation: %s", err)
        # Map HTTP client errors to CannotConnect
        error_to_raise = CannotConnect(f"Connection error: {err}")
    except InvalidAuth as err:  # Catch InvalidAuth from authenticate
        _LOGGER.warning("Authentication failed during validation: %s", err)
        # Store the original InvalidAuth exception
        error_to_raise = err
    except CannotConnect as err:  # Catch CannotConnect from authenticate
        _LOGGER.warning("Connection failed during validation: %s", err)
        # Store the original CannotConnect exception
        error_to_raise = err
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation")
        # Wrap unexpected errors in CannotConnect for the config flow
        error_to_raise = CannotConnect(f"Unexpected validation error: {err}")

    # Raise any stored error after the try block
    if error_to_raise:
        raise error_to_raise

    # Return data needed for entry creation if validation succeeds
    return {"title": f"Autoskope {data[CONF_USERNAME]}"}


class AutoskopeConfigFlow(ConfigFlowBase, domain=DOMAIN):
    """Handle a config flow for Autoskope."""

    VERSION = 1
    _entry_id: str | None = None  # Store entry_id for reauth
    entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Use a unique_id based on username@host
            unique_id = (
                f"{user_input[CONF_USERNAME]}@{user_input.get(CONF_HOST, DEFAULT_HOST)}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates=user_input)

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # Catch any other unexpected errors from validate_input
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication."""
        self._entry_id = self.context["entry_id"]  # Store entry_id from context
        return await self._show_reauth_form()

    async def _show_reauth_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the reauth form."""
        existing_entry = self.hass.config_entries.async_get_entry(self._entry_id)  # type: ignore[arg-type]
        assert existing_entry is not None

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"username": existing_entry.data[CONF_USERNAME]},
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors or {},
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password confirmation for re-authentication."""
        errors: dict[str, str] = {}
        existing_entry = self.hass.config_entries.async_get_entry(self._entry_id)  # type: ignore[arg-type]
        assert existing_entry is not None

        if user_input is not None:
            # Combine existing data (username, host) with the new password
            reauth_data = {
                CONF_USERNAME: existing_entry.data[CONF_USERNAME],
                CONF_HOST: existing_entry.data.get(
                    CONF_HOST, DEFAULT_HOST
                ),  # Ensure host is included
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            try:
                await validate_input(self.hass, reauth_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth validation")
                errors["base"] = "unknown"
            else:
                # Validation successful, update the entry
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data=reauth_data,
                )
                # Reload the entry to apply changes
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # Show form again if validation failed
        return await self._show_reauth_form(errors=errors)

    @callback
    def async_show_reconfigure_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the reconfiguration form to provide instructions."""
        assert self.entry is not None
        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={
                "username": self.entry.data[CONF_USERNAME],
                "host": self.entry.data.get(CONF_HOST, DEFAULT_HOST),
            },
            errors=errors or {},
            data_schema=vol.Schema({}),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        # Assign the fetched entry to the declared attribute
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert self.entry is not None

        if user_input is None:
            return self.async_show_reconfigure_form()

        # If the user confirms the informational step
        return self.async_abort(reason="reconfigure_successful")
