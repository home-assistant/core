"""Config flow for Evohome."""

from typing import Any

from evohomeasync2 import EvohomeClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_EXPIRES, CONF_REFRESH_TOKEN, DOMAIN

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class EvohomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Evohome config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)
            client = EvohomeClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session=session
            )
            try:
                await client.login()
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                data = {
                    **user_input,
                    CONF_ACCESS_TOKEN: client.access_token,
                    CONF_REFRESH_TOKEN: client.refresh_token,
                    CONF_EXPIRES: client.access_token_expires,
                }
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=data,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
