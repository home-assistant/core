"""Config flow for Discogs."""

from typing import Any, override

import discogs_client
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

from .const import DOMAIN

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


def _validate_token(token: str) -> tuple[str, dict[str, str]]:
    """Validate the token and return the username."""
    errors: dict[str, str] = {}
    username = ""
    try:
        client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)
        identity = client.identity()
        username = identity.name
    except discogs_client.exceptions.HTTPError:
        errors["base"] = "invalid_auth"
    except Exception:  # noqa: BLE001
        errors["base"] = "unknown"
    return username, errors
