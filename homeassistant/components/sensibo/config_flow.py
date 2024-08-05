"""Adds config flow for Sensibo integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pysensibo.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import TextSelector

from .const import DEFAULT_NAME, DOMAIN
from .util import NoDevicesError, NoUsernameError, async_validate_api

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(),
    }
)


class SensiboConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensibo integration."""

    VERSION = 2

    entry: ConfigEntry | None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Sensibo."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Sensibo."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]
            try:
                username = await async_validate_api(self.hass, api_key)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except NoDevicesError:
                errors["base"] = "no_devices"
            except NoUsernameError:
                errors["base"] = "no_username"
            else:
                assert self.entry is not None

                if username == self.entry.unique_id:
                    return self.async_update_reload_and_abort(
                        self.entry,
                        data={
                            **self.entry.data,
                            CONF_API_KEY: api_key,
                        },
                    )
                errors["base"] = "incorrect_api_key"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]
            try:
                username = await async_validate_api(self.hass, api_key)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except NoDevicesError:
                errors["base"] = "no_devices"
            except NoUsernameError:
                errors["base"] = "no_username"
            else:
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
