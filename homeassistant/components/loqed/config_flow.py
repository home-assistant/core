"""Config flow for loqed integration."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import aiohttp
from loqedAPI import loqed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import network

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


urlRegex = re.compile(
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?| \
    [A-Z0-9-]{s2,}\.?)|"
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


async def validate_input(hass, data):
    """Validate the user input allows us to connect."""
    if len(data["internal_url"]) > 5:
        if re.match(urlRegex, data["internal_url"]) is None:
            _LOGGER.error("Local HA URL is incorrect %s", data["internal_url"])
            raise ValueError("Local HA URL is incorrect")
    newdata = data
    json_config = json.loads(data["config"])
    newdata["ip"] = json_config["bridge_ip"]
    newdata["host"] = json_config["bridge_mdns_hostname"]
    newdata["bkey"] = json_config["bridge_key"]
    newdata["key_id"] = int(json_config["lock_key_local_id"])
    newdata["api_key"] = json_config["lock_key_key"]
    _LOGGER.debug("Got Info from config: %s", str(newdata))

    # 1. Checking loqed-connection
    try:
        async with aiohttp.ClientSession() as session:
            apiclient = loqed.APIClient(session, "http://" + newdata["ip"])
            api = loqed.LoqedAPI(apiclient)
            lock = await api.async_get_lock(
                newdata["api_key"], newdata["bkey"], newdata["key_id"], newdata["name"]
            )
            _LOGGER.debug("Lock details retrieved: %s", newdata["ip"])
            newdata["id"] = lock.id
            # checking getWebooks to check the bridgeKey
            await lock.getWebhooks()
    except (aiohttp.ClientError):
        _LOGGER.error("HTTP Connection error to loqed lock: %s:%s", lock.name, lock.id)
        raise CannotConnect from aiohttp.ClientError
    except Exception:
        _LOGGER.error("HTTP Connection error to loqed lock: %s:%s", lock.name, lock.id)
        raise CannotConnect from aiohttp.ClientError
    return newdata


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for loqed."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize configflow."""
        self.host = "LOQED.."

    async def async_step_zeroconf(self, discovery_info) -> FlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("HOST: %s", discovery_info.hostname)
        _LOGGER.info("HOST: %s", discovery_info.hostname)

        host = discovery_info.hostname.rstrip(".")
        async with aiohttp.ClientSession() as session:
            apiclient = loqed.APIClient(session, "http://" + host)
            api = loqed.LoqedAPI(apiclient)
            lock_data = await api.async_get_lock_details()

        # Check if already exists
        id = lock_data["bridge_mac_wifi"]
        if await self.async_set_unique_id(id) is not None:
            self.async_abort(reason="already_configured")
        self.host = host
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show userform to user."""
        try:
            internal_url = network.get_url(
                self.hass, allow_internal=True, allow_external=False, allow_ip=True
            )
            if internal_url.startswith("172"):
                internal_url = "http://<IP>:8123"
        except network.NoURLAvailableError:
            internal_url = "http://<IP>:8123"

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required("name", default="My Lock"): str,
                vol.Required("internal_url", default=internal_url): str,
                vol.Required("config"): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
            if await self.async_set_unique_id(info["id"]) is not None:
                _LOGGER.error("Aborting config: This device is already configured")
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title="LOQED Touch Smart Lock", data=user_input
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
