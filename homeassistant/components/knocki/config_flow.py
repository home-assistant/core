"""Config flow for Knocki integration."""

from __future__ import annotations

from typing import Any

from knocki import KnockiClient, KnockiConnectionError, KnockiInvalidAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class KnockiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Knocki."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = KnockiClient(session=async_get_clientsession(self.hass))
            try:
                token_response = await client.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                await self.async_set_unique_id(token_response.user_id)
                self._abort_if_unique_id_configured()
                client.token = token_response.token
                await client.link()
            except HomeAssistantError:
                # Catch the unique_id abort and reraise it to keep the code clean
                raise
            except KnockiConnectionError:
                errors["base"] = "cannot_connect"
            except KnockiInvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Error logging into the Knocki API")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_TOKEN: token_response.token,
                    },
                )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=DATA_SCHEMA,
        )
