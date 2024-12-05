"""Config flow for Digital Alchemy Synapse."""

from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow

from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from .const import DOMAIN, EVENT_NAMESPACE
from .bridge import SynapseApplication, hex_to_object
import asyncio
import logging



class SynapseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for synapse"""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the Synapse flow."""
        self.application: SynapseApplication | None = None
        self.discovery_info: dict | None = None
        self.logger = logging.getLogger(__name__)
        self.known_apps = []


    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                selected_app_name = user_input[CONF_NAME]
                selected_app_info = next(app for app in self.known_apps if app['app'] == selected_app_name)

                await self.async_set_unique_id(selected_app_info.get("unique_id"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=selected_app_info.get("title"), data=selected_app_info)
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error(ex)
                errors["base"] = "unknown"

        # Get the list of known good things
        try:
            self.known_apps = await self.identify_all()
            app_choices = {app['app']: app['title'] for app in self.known_apps}
        except Exception:
            errors["base"] = "unknown"
            app_choices = {}

        if not app_choices:
            errors["base"] = "No new applications found"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_NAME): vol.In(app_choices)}),
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        self.discovery_info = discovery_info
        try:
            # application config data from ssdp payload
            configuration_hex = discovery_info.upnp.get('configuration')

            # convert hex -> binary -> json -> dict
            info = hex_to_object(configuration_hex)

            # store for later
            self.application = info

            # hass
            id = info.get("unique_id")
            await self.async_set_unique_id(f"{id}-ssdp")
            self._abort_if_unique_id_configured()

            # configuration confirmation prompt
            self.context["title_placeholders"] = {"name": info["title"]}
            return await self.async_step_confirm()

        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="unknown_error")

    async def async_step_confirm(self, user_input=None):
        """Handle the confirmation step."""
        if user_input is not None:
            return self.async_create_entry(title=self.application["title"], data=self.application)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self.application["title"]},
            data_schema=vol.Schema({}),
        )

    async def identify_all(self):
        """Request all connected apps identify themselves"""
        # set up listener
        replies = []
        def handle_event(event):
            replies.append(event.data.get("compressed"))
        remove = self.hass.bus.async_listen(f"{EVENT_NAMESPACE}/identify", handle_event)

        # emit reload request
        self.hass.bus.async_fire(f"{EVENT_NAMESPACE}/discovery")

        # Allow half second for replies
        await asyncio.sleep(0.5)

        # Stop listening
        remove()

        # string[] -> dict[]
        return [hex_to_object(hex_str) for hex_str in replies]
