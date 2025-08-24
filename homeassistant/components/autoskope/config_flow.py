"""Config flow for the Autoskope integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow as ConfigFlowBase,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DOMAIN

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
    )
    error_to_raise: Exception | None = None

    try:
        auth_result = await api.authenticate(session=async_get_clientsession(hass))
        if not auth_result:
            _LOGGER.warning("Authentication returned False during validation")
            error_to_raise = InvalidAuth("Authentication failed")
    except aiohttp.ClientError as err:
        _LOGGER.debug("Connection error during validation: %s", err)
        error_to_raise = CannotConnect(f"Connection error: {err}")
    except InvalidAuth as err:
        _LOGGER.warning("Authentication failed during validation: %s", err)
        error_to_raise = err
    except CannotConnect as err:
        _LOGGER.warning("Connection failed during validation: %s", err)
        error_to_raise = err
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation")
        error_to_raise = CannotConnect(f"Unexpected validation error: {err}")

    if error_to_raise:
        raise error_to_raise

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
        self._entry_id = self.context["entry_id"]
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
            reauth_data = {
                CONF_USERNAME: existing_entry.data[CONF_USERNAME],
                CONF_HOST: existing_entry.data.get(CONF_HOST, DEFAULT_HOST),
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
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data=reauth_data,
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

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
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert self.entry is not None

        if user_input is None:
            return self.async_show_reconfigure_form()

        return self.async_abort(reason="reconfigure_successful")
