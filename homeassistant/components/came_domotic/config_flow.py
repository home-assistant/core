"""Config flow to configure Philips Hue."""

from __future__ import annotations

import logging
from typing import Any

from aiohue import LinkButtonNotPressed, create_app_key
from aiohue.discovery import DiscoveredHueBridge
from aiohue.util import normalize_bridge_id
import slugify as unicode_slug
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .errors import CannotConnect

LOGGER = logging.getLogger(__name__)

HUE_MANUFACTURERURL = ("http://www.philips.com", "http://www.philips-hue.com")
HUE_IGNORED_BRIDGE_NAMES = ["Home Assistant Bridge", "Espalexa"]
HUE_MANUAL_BRIDGE_ID = "manual"


class CameFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a CAME DOmotic config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CameOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CameOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the CAME Domotic flow."""
        self.came_server: DiscoveredHueBridge | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual server setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        self._async_abort_entries_match(
            {
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
        )
        self.came_server = None
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with the Hue bridge.

        Given a configured host, will ask the user to press the link button
        to connect to the bridge.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        bridge = self.came_server
        assert bridge is not None
        errors = {}
        device_name = unicode_slug.slugify(
            self.hass.config.location_name, max_length=19
        )

        try:
            app_key = await create_app_key(
                bridge.host,
                f"home-assistant#{device_name}",
                websession=aiohttp_client.async_get_clientsession(self.hass),
            )
        except LinkButtonNotPressed:
            errors["base"] = "register_failed"
        except CannotConnect:
            LOGGER.error("Error connecting to the Hue bridge at %s", bridge.host)
            return self.async_abort(reason="cannot_connect")
        except Exception:
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
            title=f"CAME Domotic {bridge.id}",
            data={
                CONF_HOST: bridge.host,
                CONF_USERNAME: app_key,
                CONF_PASSWORD: 2 if bridge.supports_v2 else 1,
            },
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import a new bridge as a config entry.

        This flow is triggered by `async_setup` for both configured and
        discovered bridges. Triggered for any bridge that does not have a
        config entry yet (based on host).

        This flow is also triggered by `async_step_discovery`.
        """
        # Check if host exists, abort if so.
        self._async_abort_entries_match({CONF_HOST: import_info[CONF_HOST]})

        bridge = None  # await self._get_bridge(import_info[CONF_HOST])
        if bridge is None:
            return self.async_abort(reason="cannot_connect")
        self.came_server = bridge
        return await self.async_step_link()


class CameOptionsFlowHandler(OptionsFlow):
    """Handle CAME Domotic options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize CAME Domotic options flow."""
        self.config_entry = config_entry
