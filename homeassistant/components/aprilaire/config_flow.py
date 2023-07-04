"""Config flow for the Aprilaire integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOG_NAME
from .coordinator import AprilaireCoordinator

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=7000): int,
    }
)

_LOGGER = logging.getLogger(LOG_NAME)


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

        errors = {}

        try:
            await self.async_set_unique_id(
                f'aprilaire_{user_input[CONF_HOST].replace(".", "")}{user_input[CONF_PORT]}'
            )
            self._abort_if_unique_id_configured()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = str(err)
        else:
            coordinator = AprilaireCoordinator(
                self.hass, user_input[CONF_HOST], user_input[CONF_PORT], _LOGGER
            )
            await coordinator.start_listen()

            async def ready_callback(ready: bool):
                if ready:
                    self.hass.data.setdefault(DOMAIN, {})[self.unique_id] = coordinator
                else:
                    _LOGGER.error("Failed to wait for ready")

                    coordinator.stop_listen()

            ready = await coordinator.wait_for_ready(ready_callback)

            if ready:
                return self.async_create_entry(title="Aprilaire", data=user_input)

            errors["base"] = "connection_failed"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
