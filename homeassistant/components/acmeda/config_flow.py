"""Config flow for Rollease Acmeda Automate Pulse Hub."""

from __future__ import annotations

from asyncio import timeout
from contextlib import suppress
from typing import Any

import aiopulse
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_ID

from .const import DOMAIN


class AcmedaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Acmeda config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_hubs: dict[str, aiopulse.Hub] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

        with suppress(TimeoutError):
            async with timeout(5):
                hubs: list[aiopulse.Hub] = [
                    hub
                    async for hub in aiopulse.Hub.discover()
                    if hub.id not in already_configured
                ]

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

    async def async_create(self, hub: aiopulse.Hub) -> ConfigFlowResult:
        """Create the Acmeda Hub entry."""
        await self.async_set_unique_id(hub.id, raise_on_progress=False)
        return self.async_create_entry(title=hub.id, data={CONF_HOST: hub.host})
