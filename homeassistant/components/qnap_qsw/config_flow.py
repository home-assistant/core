"""Adds config flow for QNAP QSW."""
from __future__ import annotations

from typing import Any

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

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.qsha: QSHA = None
        self.host: str | None = None
        self.username: str | None = None
        self.password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                host = user_input[CONF_HOST]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                self.qsha = QSHA(host=host, user=username, password=password)
                await _qnap_qsw_update(self.hass, self.qsha)

                await self.async_set_unique_id(self.qsha.serial().lower())
                self._abort_if_unique_id_configured()

                title = f"{self.qsha.product()} {self.qsha.serial()}"
                return self.async_create_entry(title=title, data=user_input)
            except LoginError:
                errors["base"] = "invalid_auth"
            except ConnectionError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


async def _qnap_qsw_update(hass, qsha):
    return await hass.async_add_executor_job(qsha.async_identify)
