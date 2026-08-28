"""Config flow for Discogs."""

from collections.abc import Mapping
from typing import Any, override

import discogs_client
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

from .const import DOMAIN, LOGGER

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
    }
)


class DiscogsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Discogs."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username, errors = await self.hass.async_add_executor_job(
                _validate_token, user_input[CONF_TOKEN]
            )
            if not errors:
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=username,
                    data={CONF_TOKEN: user_input[CONF_TOKEN]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        username, errors = await self.hass.async_add_executor_job(
            _validate_token, import_data[CONF_TOKEN]
        )
        if errors:
            return self.async_abort(reason=errors["base"])
        await self.async_set_unique_id(username)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=username,
            data={CONF_TOKEN: import_data[CONF_TOKEN]},
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
        errors: dict[str, str] = {}
        if user_input is not None:
            username, errors = await self.hass.async_add_executor_job(
                _validate_token, user_input[CONF_TOKEN]
            )
            if not errors:
                if username != self._get_reauth_entry().unique_id:
                    errors["base"] = "wrong_account"
                else:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data={CONF_TOKEN: user_input[CONF_TOKEN]},
                    )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )


def _validate_token(token: str) -> tuple[str, dict[str, str]]:
    """Validate the token and return the username."""
    errors: dict[str, str] = {}
    username = ""
    try:
        client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)
        identity = client.identity()
        username = identity.name
    except discogs_client.exceptions.HTTPError as err:
        if err.status_code == 401:
            errors["base"] = "invalid_auth"
        else:
            errors["base"] = "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected error validating Discogs token")
        errors["base"] = "unknown"
    return username, errors
