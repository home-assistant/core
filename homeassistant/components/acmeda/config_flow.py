"""Config flow for Rollease Acmeda Automate Pulse Hub."""
import asyncio
from typing import Dict, Optional

import aiopulse
import async_timeout
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN  # pylint: disable=unused-import


class AcmedaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Acmeda config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_hubs: Optional[Dict[str, aiopulse.Hub]] = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if (
            user_input is not None
            and self.discovered_hubs is not None
            # pylint: disable=unsupported-membership-test
            and user_input["id"] in self.discovered_hubs
        ):
            # pylint: disable=unsubscriptable-object
            return await self.async_create(self.discovered_hubs[user_input["id"]])

        # Already configured hosts
        already_configured = {
            entry.unique_id for entry in self._async_current_entries()
        }

        hubs = []
        try:
            with async_timeout.timeout(5):
                async for hub in aiopulse.Hub.discover():
                    if hub.id not in already_configured:
                        hubs.append(hub)
        except asyncio.TimeoutError:
            pass

        if len(hubs) == 0:
            return self.async_abort(reason="all_configured")

        if len(hubs) == 1:
            return await self.async_create(hubs[0])

        self.discovered_hubs = {hub.id: hub for hub in hubs}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("id"): vol.In(
                        {hub.id: f"{hub.id} {hub.host}" for hub in hubs}
                    )
                }
            ),
        )

    async def async_create(self, hub):
        """Create the Acmeda Hub entry."""
        await self.async_set_unique_id(hub.id, raise_on_progress=False)
        return self.async_create_entry(title=hub.id, data={"host": hub.host})
