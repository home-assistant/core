"""Adds config flow for QNAP QSW."""
from __future__ import annotations

from typing import Any

from qnap_qsw.const import DATA_SYSTEM_PRODUCT, DATA_SYSTEM_SERIAL
from qnap_qsw.homeassistant import QSHA, LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Required(CONF_USERNAME, default=""): str,
        vol.Required(CONF_PASSWORD, default=""): str,
    }
)


class QnapQswConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for QNAP QSW switch."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                qsha = QSHA(
                    host=user_input[CONF_HOST],
                    user=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                if await self.hass.async_add_executor_job(qsha.login):
                    await self.hass.async_add_executor_job(qsha.update_system_board)

                data = qsha.data()
                await self.async_set_unique_id(data[DATA_SYSTEM_SERIAL].lower())
                self._abort_if_unique_id_configured()

                title = f"{data[DATA_SYSTEM_PRODUCT]} {data[DATA_SYSTEM_SERIAL]}"
                return self.async_create_entry(title=title, data=user_input)
            except LoginError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
