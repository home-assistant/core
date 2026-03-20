"""Config flow for the PJLink integration."""

from __future__ import annotations

import logging
from typing import Any

from pypjlink import Projector
from pypjlink.projector import ProjectorError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=4352): cv.port,
        vol.Optional(CONF_PASSWORD): str,
    }
)


def validate_projector_connection(
    host: str, port: int | None, password: str | None
) -> dict[str, Any]:
    """Validate that we can connect to the projector."""
    projector = Projector.from_address(host, port)
    projector.authenticate(password)
    return {"title": projector.get_name()}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    try:
        info = await hass.async_add_executor_job(
            validate_projector_connection,
            data[CONF_HOST],
            data[CONF_PORT],
            data.get(CONF_PASSWORD),
        )
    except (TimeoutError, OSError) as e:
        raise CannotConnect from e
    except (RuntimeError, ProjectorError) as e:
        raise InvalidAuth from e

    return {"title": info["title"]}


class PJLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PJLink."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        _LOGGER.warning(
            "Configuration of the PJLink integration in YAML is deprecated and "
            "will be removed a future version of Home Assistant; "
            "Your existing configuration has been imported into the UI automatically "
            "and can be safely removed from your configuration.yaml file"
        )
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                return self.async_abort(reason="already_configured")
        if CONF_PORT not in import_config:
            import_config[CONF_PORT] = 4352
        return await self.async_step_user(import_config)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
