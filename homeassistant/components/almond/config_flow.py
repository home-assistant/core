"""Config flow to connect with Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError
import async_timeout
from pyalmond import AlmondLocalAuth, WebAlmondAPI
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries, core, data_entry_flow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import DOMAIN as ALMOND_DOMAIN, TYPE_LOCAL, TYPE_OAUTH2


async def async_verify_local_connection(hass: core.HomeAssistant, host: str):
    """Verify that a local connection works."""
    websession = aiohttp_client.async_get_clientsession(hass)
    api = WebAlmondAPI(AlmondLocalAuth(host, websession))

    try:
        with async_timeout.timeout(10):
            await api.async_list_apps()

        return True
    except (asyncio.TimeoutError, ClientError):
        return False


@config_entries.HANDLERS.register(ALMOND_DOMAIN)
class AlmondFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
    """Implementation of the Almond OAuth2 config flow."""

    DOMAIN = ALMOND_DOMAIN

    host = None
    hassio_discovery = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "profile user-read user-read-results user-exec-command"}

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        # Only allow 1 instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)

    async def async_step_auth(self, user_input=None):
        """Handle authorize step."""
        result = await super().async_step_auth(user_input)

        if result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP:
            self.host = str(URL(result["url"]).with_path("me"))

        return result

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        data["type"] = TYPE_OAUTH2
        data["host"] = self.host
        return self.async_create_entry(title=self.flow_impl.name, data=data)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import data."""
        # Only allow 1 instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not await async_verify_local_connection(self.hass, user_input["host"]):
            self.logger.warning(
                "Aborting import of Almond because we're unable to connect"
            )
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title="Configuration.yaml",
            data={"type": TYPE_LOCAL, "host": user_input["host"]},
        )

    async def async_step_hassio(self, discovery_info):
        """Receive a Hass.io discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.hassio_discovery = discovery_info

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm a Hass.io discovery."""
        data = self.hassio_discovery

        if user_input is not None:
            return self.async_create_entry(
                title=data["addon"],
                data={
                    "is_hassio": True,
                    "type": TYPE_LOCAL,
                    "host": f"http://{data['host']}:{data['port']}",
                },
            )

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": data["addon"]},
            data_schema=vol.Schema({}),
        )
