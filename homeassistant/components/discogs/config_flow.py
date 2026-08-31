"""Config flow for Discogs."""

from typing import Any, override

import discogs_client
import requests
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
            user_id, username, errors = await self.hass.async_add_executor_job(
                _validate_token, user_input[CONF_TOKEN]
            )
            if not errors:
                await self.async_set_unique_id(str(user_id))
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
        user_id, username, errors = await self.hass.async_add_executor_job(
            _validate_token, import_data[CONF_TOKEN]
        )
        if errors:
            return self.async_abort(reason=errors["base"])
        await self.async_set_unique_id(str(user_id))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data.get("name") or username,
            data={CONF_TOKEN: import_data[CONF_TOKEN]},
        )


def _validate_token(token: str) -> tuple[int | None, str, dict[str, str]]:
    """Validate the token and return the user ID, username, and errors."""
    errors: dict[str, str] = {}
    user_id = None
    username = ""
    try:
        client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)
        identity = client.identity()
        user_id = identity.id
        username = identity.name
    except discogs_client.exceptions.HTTPError as err:
        if err.status_code == 401:
            errors["base"] = "invalid_auth"
        else:
            errors["base"] = "cannot_connect"
    except requests.RequestException:
        errors["base"] = "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected error validating Discogs token")
        errors["base"] = "unknown"
    return user_id, username, errors
