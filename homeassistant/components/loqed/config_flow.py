"""Config flow for loqed integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
from loqedAPI import cloud_loqed, loqed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_NAME, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Loqed."""

    VERSION = 1
    DOMAIN = DOMAIN
    _host: str | None = None

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect."""

        # 1. Checking loqed-connection
        try:
            session = async_get_clientsession(hass)
            cloud_api_client = cloud_loqed.CloudAPIClient(
                session,
                data[CONF_API_TOKEN],
            )
            cloud_client = cloud_loqed.LoqedCloudAPI(cloud_api_client)
            lock_data = await cloud_client.async_get_locks()
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP Connection error to loqed API")
            raise CannotConnect from err

        try:
            selected_lock = next(
                lock
                for lock in lock_data["data"]
                if lock["bridge_ip"] == self._host or lock["name"] == data.get("name")
            )

            apiclient = loqed.APIClient(session, f"http://{selected_lock['bridge_ip']}")
            api = loqed.LoqedAPI(apiclient)
            lock = await api.async_get_lock(
                selected_lock["backend_key"],
                selected_lock["bridge_key"],
                selected_lock["local_id"],
                selected_lock["bridge_ip"],
            )

            # checking getWebooks to check the bridgeKey
            await lock.getWebhooks()
            return {
                "lock_key_key": selected_lock["key_secret"],
                "bridge_key": selected_lock["bridge_key"],
                "lock_key_local_id": selected_lock["local_id"],
                "bridge_mdns_hostname": selected_lock["bridge_hostname"],
                "bridge_ip": selected_lock["bridge_ip"],
                "name": selected_lock["name"],
                "id": selected_lock["id"],
            }
        except StopIteration:
            raise InvalidAuth from StopIteration
        except aiohttp.ClientError:
            _LOGGER.error("HTTP Connection error to loqed lock")
            raise CannotConnect from aiohttp.ClientError

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        self._host = host

        session = async_get_clientsession(self.hass)
        apiclient = loqed.APIClient(session, f"http://{host}")
        api = loqed.LoqedAPI(apiclient)
        lock_data = await api.async_get_lock_details()

        # Check if already exists
        await self.async_set_unique_id(lock_data["bridge_mac_wifi"])
        self._abort_if_unique_id_configured({CONF_HOST: host})

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show userform to user."""
        user_data_schema = (
            vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                }
            )
            if self._host
            else vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_API_TOKEN): str,
                }
            )
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=user_data_schema,
                description_placeholders={
                    "config_url": "https://integrations.production.loqed.com/personal-access-tokens",
                },
            )

        errors = {}

        try:
            info = await self.validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        else:
            await self.async_set_unique_id(
                re.sub(
                    r"LOQED-([a-f0-9]+)\.local", r"\1", info["bridge_mdns_hostname"]
                ),
                raise_on_progress=False,
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="LOQED Touch Smart Lock",
                data=(
                    user_input | {CONF_WEBHOOK_ID: webhook.async_generate_id()} | info
                ),
            )

        return self.async_show_form(
            step_id="user",
            data_schema=user_data_schema,
            errors=errors,
            description_placeholders={
                "config_url": "https://integrations.production.loqed.com/personal-access-tokens",
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
