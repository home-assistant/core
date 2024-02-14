"""Config flow to configure qnap component."""
from __future__ import annotations

import logging
from typing import Any

from qnapstats import QNAPStats
from requests.exceptions import ConnectTimeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

_LOGGER = logging.getLogger(__name__)


class QnapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Qnap configuration flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            protocol = "https" if user_input[CONF_SSL] else "http"
            api = QNAPStats(
                host=f"{protocol}://{host}",
                port=user_input[CONF_PORT],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                verify_ssl=user_input[CONF_VERIFY_SSL],
                timeout=DEFAULT_TIMEOUT,
            )
            try:
                stats = await self.hass.async_add_executor_job(api.get_system_stats)
            except ConnectTimeout:
                errors["base"] = "cannot_connect"
            except TypeError:
                errors["base"] = "invalid_auth"
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error(error)
                errors["base"] = "unknown"
            else:
                unique_id = stats["system"]["serial_number"]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = stats["system"]["name"]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )
