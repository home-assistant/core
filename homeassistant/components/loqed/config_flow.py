"""Config flow for loqed integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from loqedAPI import loqed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], zeroconf_host: str | None
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    newdata = data
    json_config = json.loads(data["config"])
    newdata["ip"] = json_config["bridge_ip"]
    newdata["host"] = json_config["bridge_mdns_hostname"]
    newdata["bkey"] = json_config["bridge_key"]
    newdata["key_id"] = int(json_config["lock_key_local_id"])
    newdata["api_key"] = json_config["lock_key_key"]

    if zeroconf_host is not None and zeroconf_host != newdata["host"]:
        raise InvalidAuth(
            f"Got config for {newdata['host']} while configuring {zeroconf_host} "
        )

    # 1. Checking loqed-connection
    try:
        session = async_get_clientsession(hass)

        apiclient = loqed.APIClient(session, "http://" + newdata["ip"])
        api = loqed.LoqedAPI(apiclient)
        lock = await api.async_get_lock(
            newdata["api_key"], newdata["bkey"], newdata["key_id"], newdata["host"]
        )
        newdata["id"] = lock.id
        # checking getWebooks to check the bridgeKey
        await lock.getWebhooks()
    except (aiohttp.ClientError):
        _LOGGER.error("HTTP Connection error to loqed lock")
        raise CannotConnect from aiohttp.ClientError
    except Exception:
        raise CannotConnect from Exception
    return newdata


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for loqed."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the ConfigFlow for the LOQED integration."""
        self._host: str | None = None

    async def async_step_zeroconf(self, discovery_info) -> FlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.hostname.rstrip(".")

        session = async_get_clientsession(self.hass)
        apiclient = loqed.APIClient(session, "http://" + self._host)
        api = loqed.LoqedAPI(apiclient)
        lock_data = await api.async_get_lock_details()

        # Check if already exists
        await self.async_set_unique_id(lock_data["bridge_mac_wifi"])
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show userform to user."""
        user_data_schema = vol.Schema(
            {
                vol.Required("config"): str,
            }
        )
        self.context["title_placeholders"] = {CONF_HOST: self._host}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=user_data_schema,
                description_placeholders={
                    CONF_HOST: self._host,
                    "config_url": "https://app.loqed.com/API-Config",
                },
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input, self._host)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="LOQED Touch Smart Lock", data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=user_data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
