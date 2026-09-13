"""Config flow for the Arris TG2492LG integration."""

from collections.abc import Mapping
from typing import Any, override

from aiohttp import ClientConnectionError, ClientResponseError
from arris_tg2492lg import ConnectBox
from arris_tg2492lg.exception import InvalidCredentialError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class ArrisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Arris TG2492LG integration."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        try:
            await self._async_validate(user_input)
        except InvalidCredentialError:
            errors["base"] = "invalid_auth"
        except ClientResponseError as err:
            errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
        except ClientConnectionError:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        reauth_entry = self._get_reauth_entry()

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        try:
            await self._async_validate(reauth_entry.data | user_input)
        except InvalidCredentialError:
            errors["base"] = "invalid_auth"
        except ClientResponseError as err:
            errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
        except ClientConnectionError:
            errors["base"] = "cannot_connect"
        else:
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from legacy YAML configuration."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            await self._async_validate(import_data)
        except InvalidCredentialError:
            return self.async_abort(reason="invalid_auth")
        except ClientResponseError as err:
            return self.async_abort(
                reason="invalid_auth" if err.status == 401 else "cannot_connect"
            )
        except ClientConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=import_data[CONF_HOST],
            data=import_data,
        )

    async def _async_validate(self, user_input: dict[str, Any]) -> None:
        """Log in to the router to validate the given configuration."""
        connect_box = ConnectBox(
            async_get_clientsession(self.hass),
            f"http://{user_input[CONF_HOST]}",
            user_input[CONF_PASSWORD],
        )
        await connect_box.async_login()
