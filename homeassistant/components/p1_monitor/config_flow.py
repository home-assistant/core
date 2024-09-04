"""Config flow for P1 Monitor integration."""

from __future__ import annotations

from typing import Any

from p1monitor import P1Monitor, P1MonitorError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector

from .const import DOMAIN


class P1MonitorFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for P1 Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                async with P1Monitor(
                    host=user_input[CONF_HOST], session=session
                ) as client:
                    await client.smartmeter()
            except P1MonitorError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="P1 Monitor",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): TextSelector(),
                }
            ),
            errors=errors,
        )
