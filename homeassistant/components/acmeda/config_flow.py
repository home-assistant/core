"""Config flow for Rollease Acmeda Automate Pulse Hub."""
from __future__ import annotations

import asyncio
from contextlib import suppress

import aiopulse
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID

from .const import DOMAIN


class AcmedaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Acmeda config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_hubs: dict[str, aiopulse.Hub] | None = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if (
            user_input is not None
            and self.discovered_hubs is not None
            and user_input[CONF_ID] in self.discovered_hubs
        ):
            return await self.async_create(self.discovered_hubs[user_input[CONF_ID]])

        # Already configured hosts
        already_configured = {
            entry.unique_id for entry in self._async_current_entries()
        }

        hubs = []
        with suppress(asyncio.TimeoutError):
            async with async_timeout.timeout(5):
                async for hub in aiopulse.Hub.discover():
                    if hub.id not in already_configured:
                        hubs.append(hub)

        if not hubs:
            return self.async_abort(reason="no_devices_found")

        if len(hubs) == 1:
            return await self.async_create(hubs[0])

        self.discovered_hubs = {hub.id: hub for hub in hubs}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): vol.In(
                        {hub.id: f"{hub.id} {hub.host}" for hub in hubs}
                    )
                }
            ),
        )

    async def async_create(self, hub):
        """Create the Acmeda Hub entry."""
        await self.async_set_unique_id(hub.id, raise_on_progress=False)
        return self.async_create_entry(title=hub.id, data={CONF_HOST: hub.host})
