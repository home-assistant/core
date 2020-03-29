"""Config flow for Rollease Acmeda Automate Pulse Hub."""
import asyncio
from typing import Dict, Optional

import aiopulse
import async_timeout
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN, LOGGER  # pylint: disable=unused-import
from .errors import AuthenticationRequired, CannotConnect


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
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if (
            user_input is not None
            and self.discovered_hubs is not None
            # pylint: disable=unsupported-membership-test
            and user_input["id"] in self.discovered_hubs
        ):
            # pylint: disable=unsubscriptable-object
            self.hub = self.discovered_hubs[user_input["id"]]
            await self.async_set_unique_id(self.hub.id, raise_on_progress=False)
            # We pass user input to link so it will attempt to link right away
            return await self.async_step_link({})

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
        already_configured = self._async_current_ids(False)
        hubs = [hub for hub in hubs if hub.id not in already_configured]

        if not hubs:
            return self.async_abort(reason="all_configured")

        if len(hubs) == 1:
            self.hub = hubs[0]
            await self.async_set_unique_id(self.hub.id, raise_on_progress=False)
            return await self.async_step_link()

        self.discovered_hubs = {hub.id: hub for hub in hubs}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required("id"): vol.In({hub.id: hub.host for hub in hubs})}
            ),
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Acmeda Hub."""
        hub = self.hub
        assert hub is not None
        errors = {}

        try:
            # Can happen if we come from import.
            if self.unique_id is None:
                await self.async_set_unique_id(hub.id, raise_on_progress=False)

            return self.async_create_entry(title=hub.host, data={"host": hub.host},)
        except AuthenticationRequired:
            errors["base"] = "register_failed"

        except CannotConnect:
            LOGGER.error("Error connecting to the Acmeda Pulse hub at %s", hub.host)
            errors["base"] = "linking"

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Unknown error connecting with Acmeda Pulse hub at %s", hub.host
            )
            errors["base"] = "linking"

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_import(self, import_info):
        """Import a new hub as a config entry.

        This flow is triggered by `async_setup` for both configured and
        discovered bridges. Triggered for any bridge that does not have a
        config entry yet (based on host).

        This flow is also triggered by `async_step_discovery`.
        """
        # Check if host exists, abort if so.
        if any(
            import_info["host"] == entry.data["host"]
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")

        self.hub = aiopulse.Hub(import_info["host"])
        return await self.async_step_link()
