"""Config flow for loqed integration."""
from __future__ import annotations

import logging
import re

from loqedAPI import loqed

from homeassistant.components import webhook
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_WEBHOOK_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class ConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Loqed."""

    VERSION = 1
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host

        session = async_get_clientsession(self.hass)
        apiclient = loqed.APIClient(session, f"http://{host}")
        api = loqed.LoqedAPI(apiclient)
        lock_data = await api.async_get_lock_details()

        # Check if already exists
        await self.async_set_unique_id(lock_data["bridge_mac_wifi"])
        self._abort_if_unique_id_configured({CONF_HOST: host})
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        session = async_get_clientsession(self.hass)
        res = await session.request(
            "GET",
            "https://app.loqed.com/API/integration_oauth3/retrieve_lock_data.php",
            headers={"Authorization": f"Bearer {data['token']['access_token']}"},
        )
        lock_data = await res.json(content_type="text/html")

        await self.async_set_unique_id(
            re.sub(
                r"LOQED-([a-f0-9]+)\.local", r"\1", lock_data["bridge_mdns_hostname"]
            )
        )

        config = data | {CONF_WEBHOOK_ID: webhook.async_generate_id()} | lock_data

        return self.async_create_entry(title=self.flow_impl.name, data=config)
