"""Config flow for the Sony Projector integration."""

import logging
from typing import Any, override

import probatio
import pysdcp

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})


class SonyProjectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony Projector."""

    VERSION = 1

    async def _async_can_connect(self, host: str) -> bool:
        """Return whether the projector answers a power status request."""
        projector = pysdcp.Projector(host)
        try:
            await self.hass.async_add_executor_job(projector.get_power)
        # pySDCP raises bare Exception for timeouts and projector error replies,
        # so connection failures can't be told apart from other errors.
        except Exception:
            _LOGGER.debug("Failed to connect to %s", host, exc_info=True)
            return False
        return True

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host: str = user_input[CONF_HOST]
            self._async_abort_entries_match({CONF_HOST: host})

            if await self._async_can_connect(host):
                # Another flow may have set up the projector during the validation.
                self._async_abort_entries_match({CONF_HOST: host})
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={CONF_HOST: host}
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a YAML platform."""
        host: str = import_data[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})

        if not await self._async_can_connect(host):
            return self.async_abort(reason="cannot_connect")

        # A user flow may have set up the projector during the validation.
        self._async_abort_entries_match({CONF_HOST: host})
        return self.async_create_entry(
            title=import_data[CONF_NAME], data={CONF_HOST: host}
        )
