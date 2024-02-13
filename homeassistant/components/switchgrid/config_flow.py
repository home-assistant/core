"""Config flow for Switchgrid integration."""
from __future__ import annotations

from asyncio import timeout
from typing import Any

from switchgrid_python_client import SwitchgridClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchgrid."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        session = async_get_clientsession(self.hass)
        client = SwitchgridClient(session)

        try:
            async with timeout(10):
                await client.update()
                if client.last_updated is None:
                    return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="Switchgrid", data=user_input)
