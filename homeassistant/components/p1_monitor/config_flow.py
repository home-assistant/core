"""Config flow for P1 Monitor integration."""

from __future__ import annotations

from typing import Any

from p1monitor import P1Monitor, P1MonitorError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import DOMAIN


class P1MonitorFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for P1 Monitor."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                async with P1Monitor(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    session=session,
                ) as client:
                    await client.smartmeter()
            except P1MonitorError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="P1 Monitor",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): TextSelector(),
                    vol.Required(CONF_PORT, default=80): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=65535, mode=NumberSelectorMode.BOX
                            ),
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            errors=errors,
        )
