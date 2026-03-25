"""Config flow for the PJLink integration."""

from __future__ import annotations

import logging
from typing import Any

from pypjlink import Projector
from pypjlink.projector import ProjectorError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
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
) -> str:
    """Validate that we can connect to the projector."""
    projector = Projector.from_address(host, port)
    projector.authenticate(password)
    return projector.get_name()


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
                projector_name = await self.hass.async_add_executor_job(
                    validate_projector_connection,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input.get(CONF_PASSWORD),
                )
            except TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except RuntimeError, ProjectorError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=projector_name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""

        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        try:
            projector_name = await self.hass.async_add_executor_job(
                validate_projector_connection,
                import_config[CONF_HOST],
                import_config.get(CONF_PORT, 4352),
                import_config.get(CONF_PASSWORD),
            )
        except TimeoutError, OSError:
            return self.async_abort(reason="cannot_connect")
        except RuntimeError, ProjectorError:
            return self.async_abort(reason="invalid_auth")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        else:
            return self.async_create_entry(
                title=import_config.get(CONF_NAME, projector_name), data=import_config
            )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
