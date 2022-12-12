"""Config flow for EnergyZero integration."""
from __future__ import annotations

from typing import Any

from energyzero import EnergyZero, EnergyZeroError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import CONF_GAS, DOMAIN


class EnergyZeroFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for EnergyZero integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            today = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            try:
                async with EnergyZero(session=session) as client:
                    await client.energy_prices(start_date=today, end_date=today)
            except EnergyZeroError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="EnergyZero",
                    data={
                        CONF_GAS: user_input[CONF_GAS],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_GAS, default=False): bool,
                }
            ),
            errors=errors,
        )
