"""Config flow for FYTA integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class FytaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fyta."""

    VERSION = 1
    _entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            fyta = FytaConnector(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

            try:
                await fyta.login()
            except FytaConnectionError:
                errors["base"] = "cannot_connect"
            except FytaAuthentificationError:
                errors["base"] = "invalid_auth"
            except FytaPasswordError:
                errors["base"] = "invalid_auth"
                errors[CONF_PASSWORD] = "password_error"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            finally:
                await fyta.client.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle flow upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}
        assert self._entry is not None

        if user_input:
            fyta = FytaConnector(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            credentials: dict[str, str | datetime] = {}

            try:
                credentials = await fyta.login()
                await fyta.client.close()
            except FytaConnectionError:
                errors["base"] = "cannot_connect"
            except FytaAuthentificationError:
                errors["base"] = "invalid_auth"
            except FytaPasswordError:
                errors["base"] = "invalid_auth"
                errors[CONF_PASSWORD] = "password_error"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                user_input |= credentials

                return self.async_update_reload_and_abort(self._entry, data={**self._entry.data, **user_input})

        data_schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA,
            {CONF_USERNAME: self._entry.data[CONF_USERNAME], **(user_input or {})},
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            description_placeholders={"FYTA username": self._entry.data[CONF_USERNAME]},
            errors=errors,
        )
