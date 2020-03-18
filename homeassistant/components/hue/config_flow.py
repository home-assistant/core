"""Config flow to configure Philips Hue."""
import asyncio
from typing import Dict, Optional
from urllib.parse import urlparse

import aiohue
from aiohue.discovery import discover_nupnp, normalize_bridge_id
import async_timeout
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client

from .bridge import authenticate_bridge
from .const import (  # pylint: disable=unused-import
    CONF_ALLOW_HUE_GROUPS,
    DOMAIN,
    LOGGER,
)
from .errors import AuthenticationRequired, CannotConnect

HUE_MANUFACTURERURL = "http://www.philips.com"
HUE_IGNORED_BRIDGE_NAMES = ["Home Assistant Bridge", "Espalexa"]


class HueFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hue config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize the Hue flow."""
        self.bridge: Optional[aiohue.Bridge] = None
        self.discovered_bridges: Optional[Dict[str, aiohue.Bridge]] = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    @core.callback
    def _async_get_bridge(self, host: str, bridge_id: Optional[str] = None):
        """Return a bridge object."""
        if bridge_id is not None:
            bridge_id = normalize_bridge_id(bridge_id)

        return aiohue.Bridge(
            host,
            websession=aiohttp_client.async_get_clientsession(self.hass),
            bridge_id=bridge_id,
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if (
            user_input is not None
            and self.discovered_bridges is not None
            # pylint: disable=unsupported-membership-test
            and user_input["id"] in self.discovered_bridges
        ):
            # pylint: disable=unsubscriptable-object
            self.bridge = self.discovered_bridges[user_input["id"]]
            await self.async_set_unique_id(self.bridge.id, raise_on_progress=False)
            # We pass user input to link so it will attempt to link right away
            return await self.async_step_link({})

        try:
            with async_timeout.timeout(5):
                bridges = await discover_nupnp(
                    websession=aiohttp_client.async_get_clientsession(self.hass)
                )
        except asyncio.TimeoutError:
            return self.async_abort(reason="discover_timeout")

        if not bridges:
            return self.async_abort(reason="no_bridges")

        # Find already configured hosts
        already_configured = self._async_current_ids(False)
        bridges = [bridge for bridge in bridges if bridge.id not in already_configured]

        if not bridges:
            return self.async_abort(reason="all_configured")

        if len(bridges) == 1:
            self.bridge = bridges[0]
            await self.async_set_unique_id(self.bridge.id, raise_on_progress=False)
            return await self.async_step_link()

        self.discovered_bridges = {bridge.id: bridge for bridge in bridges}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("id"): vol.In(
                        {bridge.id: bridge.host for bridge in bridges}
                    )
                }
            ),
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Hue bridge.

        Given a configured host, will ask the user to press the link button
        to connect to the bridge.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        bridge = self.bridge
        assert bridge is not None
        errors = {}

        try:
            await authenticate_bridge(self.hass, bridge)

            # Can happen if we come from import.
            if self.unique_id is None:
                await self.async_set_unique_id(
                    normalize_bridge_id(bridge.id), raise_on_progress=False
                )

            return self.async_create_entry(
                title=bridge.config.name,
                data={
                    "host": bridge.host,
                    "username": bridge.username,
                    CONF_ALLOW_HUE_GROUPS: False,
                },
            )
        except AuthenticationRequired:
            errors["base"] = "register_failed"

        except CannotConnect:
            LOGGER.error("Error connecting to the Hue bridge at %s", bridge.host)
            errors["base"] = "linking"

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Unknown error connecting with Hue bridge at %s", bridge.host
            )
            errors["base"] = "linking"

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Hue bridge.

        This flow is triggered by the SSDP component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # Filter out non-Hue bridges #1
        if discovery_info.get(ssdp.ATTR_UPNP_MANUFACTURER_URL) != HUE_MANUFACTURERURL:
            return self.async_abort(reason="not_hue_bridge")

        # Filter out non-Hue bridges #2
        if any(
            name in discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME, "")
            for name in HUE_IGNORED_BRIDGE_NAMES
        ):
            return self.async_abort(reason="not_hue_bridge")

        if (
            ssdp.ATTR_SSDP_LOCATION not in discovery_info
            or ssdp.ATTR_UPNP_SERIAL not in discovery_info
        ):
            return self.async_abort(reason="not_hue_bridge")

        host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname

        bridge = self._async_get_bridge(host, discovery_info[ssdp.ATTR_UPNP_SERIAL])

        await self.async_set_unique_id(bridge.id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: bridge.host})

        self.bridge = bridge
        return await self.async_step_link()

    async def async_step_homekit(self, homekit_info):
        """Handle HomeKit discovery."""
        bridge = self._async_get_bridge(
            homekit_info["host"], homekit_info["properties"]["id"]
        )

        await self.async_set_unique_id(bridge.id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: bridge.host})

        self.bridge = bridge
        return await self.async_step_link()

    async def async_step_import(self, import_info):
        """Import a new bridge as a config entry.

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

        self.bridge = self._async_get_bridge(import_info["host"])
        return await self.async_step_link()
