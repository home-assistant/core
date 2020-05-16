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
        self.hub: Optional[aiopulse.Hub] = None
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
            self.hub = self.discovered_hubs[user_input["id"]]
            return await self.async_step_create()

        hubs = []
        try:
            with async_timeout.timeout(5):
                async for hub in aiopulse.Hub.discover():
                    hubs.append(hub)
        except asyncio.TimeoutError:
            if len(hubs) == 0:
                return self.async_abort(reason="discover_timeout")

        if not hubs:
            return self.async_abort(reason="no_hubs")

        # Find already configured hosts
        already_configured = {
            entry.data["host"] for entry in self._async_current_entries()
        }
        hubs = [hub for hub in hubs if hub.host not in already_configured]

        if not hubs:
            return self.async_abort(reason="all_configured")

        if len(hubs) == 1:
            self.hub = hubs[0]
            return await self.async_step_create()

        self.discovered_hubs = {hub.id: hub for hub in hubs}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("id"): vol.In({hub.id: hub.host for hub in hubs})}
            ),
        )

    async def async_step_create(self, user_input=None):
        """Create the Acmeda Hub entry."""
        hub = self.hub
        assert hub is not None

        await self.async_set_unique_id(self.hub.id, raise_on_progress=False)

        title = f"{hub.id} ({hub.host})"

        return self.async_create_entry(title=title, data={"host": hub.host})
