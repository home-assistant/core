"""Config flow for the PJLink integration."""

import logging
from typing import Any, override

import probatio
from pypjlink import Projector
from pypjlink.projector import ProjectorError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
    }
)


def validate_projector_connection(
    host: str, port: int | None, password: str | None
) -> str:
    """Validate that we can connect to the projector."""
    with Projector.from_address(host, port) as projector:
        projector.authenticate(password)
        return projector.get_name()


class PJLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PJLink."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
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
