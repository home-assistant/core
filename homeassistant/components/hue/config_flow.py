"""Config flow to configure Philips Hue."""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import aiohue
from aiohue.discovery import discover_nupnp, normalize_bridge_id
import async_timeout
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .bridge import authenticate_bridge
from .const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
    DEFAULT_ALLOW_HUE_GROUPS,
    DEFAULT_ALLOW_UNREACHABLE,
    DOMAIN,
    LOGGER,
)
from .errors import AuthenticationRequired, CannotConnect

HUE_MANUFACTURERURL = ("http://www.philips.com", "http://www.philips-hue.com")
HUE_IGNORED_BRIDGE_NAMES = ["Home Assistant Bridge", "Espalexa"]
HUE_MANUAL_BRIDGE_ID = "manual"


class HueFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hue config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HueOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Hue flow."""
        self.bridge: aiohue.Bridge | None = None
        self.discovered_bridges: dict[str, aiohue.Bridge] | None = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    @core.callback
    def _async_get_bridge(self, host: str, bridge_id: str | None = None):
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
        # Check if user chooses manual entry
        if user_input is not None and user_input["id"] == HUE_MANUAL_BRIDGE_ID:
            return await self.async_step_manual()

        if (
            user_input is not None
            and self.discovered_bridges is not None
            and user_input["id"] in self.discovered_bridges
        ):
            self.bridge = self.discovered_bridges[user_input["id"]]
            await self.async_set_unique_id(self.bridge.id, raise_on_progress=False)
            return await self.async_step_link()

        # Find / discover bridges
        try:
            with async_timeout.timeout(5):
                bridges = await discover_nupnp(
                    websession=aiohttp_client.async_get_clientsession(self.hass)
                )
        except asyncio.TimeoutError:
            return self.async_abort(reason="discover_timeout")

        if bridges:
            # Find already configured hosts
            already_configured = self._async_current_ids(False)
            bridges = [
                bridge for bridge in bridges if bridge.id not in already_configured
            ]
            self.discovered_bridges = {bridge.id: bridge for bridge in bridges}

        if not self.discovered_bridges:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("id"): vol.In(
                        {
                            **{bridge.id: bridge.host for bridge in bridges},
                            HUE_MANUAL_BRIDGE_ID: "Manually add a Hue Bridge",
                        }
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual bridge setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            )

        if any(
            user_input["host"] == entry.data.get("host")
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")

        self.bridge = self._async_get_bridge(user_input[CONF_HOST])
        return await self.async_step_link()

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
        except AuthenticationRequired:
            errors["base"] = "register_failed"
        except CannotConnect:
            LOGGER.error("Error connecting to the Hue bridge at %s", bridge.host)
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Unknown error connecting with Hue bridge at %s", bridge.host
            )
            errors["base"] = "linking"

        if errors:
            return self.async_show_form(step_id="link", errors=errors)

        # Can happen if we come from import or manual entry
        if self.unique_id is None:
            await self.async_set_unique_id(
                normalize_bridge_id(bridge.id), raise_on_progress=False
            )

        return self.async_create_entry(
            title=bridge.config.name,
            data={CONF_HOST: bridge.host, CONF_USERNAME: bridge.username},
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Hue bridge.

        This flow is triggered by the SSDP component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # Filter out non-Hue bridges #1
        if (
            discovery_info.get(ssdp.ATTR_UPNP_MANUFACTURER_URL)
            not in HUE_MANUFACTURERURL
        ):
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
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: bridge.host}, reload_on_update=False
        )

        self.bridge = bridge
        return await self.async_step_link()

    async def async_step_homekit(self, discovery_info):
        """Handle a discovered Hue bridge on HomeKit.

        The bridge ID communicated over HomeKit differs, so we cannot use that
        as the unique identifier. Therefore, this method uses discovery without
        a unique ID.
        """
        self.bridge = self._async_get_bridge(discovery_info[CONF_HOST])
        await self._async_handle_discovery_without_unique_id()
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
            import_info["host"] == entry.data.get("host")
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")

        self.bridge = self._async_get_bridge(import_info["host"])
        return await self.async_step_link()


class HueOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Hue options."""

    def __init__(self, config_entry):
        """Initialize Hue options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Hue options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOW_HUE_GROUPS,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_HUE_GROUPS, DEFAULT_ALLOW_HUE_GROUPS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ALLOW_UNREACHABLE,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_UNREACHABLE, DEFAULT_ALLOW_UNREACHABLE
                        ),
                    ): bool,
                }
            ),
        )
