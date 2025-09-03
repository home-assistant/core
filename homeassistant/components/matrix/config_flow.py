"""Config flow for Matrix integration."""

from __future__ import annotations

import logging
from typing import Any

from nio import AsyncClient, LoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_HOMESERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOMESERVER): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = AsyncClient(
        homeserver=data[CONF_HOMESERVER],
        user=data[CONF_USERNAME],
        ssl=data[CONF_VERIFY_SSL],
    )

    login_response = await client.login(data[CONF_PASSWORD])
    if isinstance(login_response, LoginError):
        await client.close()
        raise ConnectionError

    # Get user info to validate connection
    whoami_response = await client.whoami()
    if hasattr(whoami_response, "user_id"):
        user_id = whoami_response.user_id
    else:
        user_id = data[CONF_USERNAME]

    await client.close()
    return {"title": user_id, "user_id": user_id}


class MatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["user_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        try:
            info = await validate_input(self.hass, import_data)
        except Exception:
            _LOGGER.exception("Failed to validate imported YAML config")
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(info["user_id"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{info['title']} (from YAML)",
            data=import_data,
        )
