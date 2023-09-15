"""Config flow for the Aprilaire integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import AprilaireCoordinator

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=7000): cv.port,
    }
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aprilaire."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        coordinator = AprilaireCoordinator(
            self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
        )
        await coordinator.start_listen()

        async def ready_callback(ready: bool):
            if not ready:
                _LOGGER.error("Failed to wait for ready")

        ready = await coordinator.wait_for_ready(ready_callback)

        coordinator.stop_listen()

        if ready:
            return self.async_create_entry(title="Aprilaire", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={"base": "connection_failed"},
        )
