"""Config flow for the Paperless-ngx integration."""

from __future__ import annotations

import logging
from typing import Any

from pypaperless import Paperless
from pypaperless.exceptions import InitializationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


class PaperlessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paperless-ngx."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                }
            )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = Paperless(user_input[CONF_HOST], user_input[CONF_ACCESS_TOKEN])
                await client.initialize()
            except OSError as err:
                if "Connect call failed" in str(err) or "Domain name not found" in str(
                    err
                ):
                    errors[CONF_HOST] = "cannot_connect_host"
            except InitializationError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Paperless-ngx", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
