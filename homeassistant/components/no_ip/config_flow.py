"""Adds config flow for No-IP.com integration."""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import aiohttp
from aiohttp.hdrs import AUTHORIZATION, USER_AGENT
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DEFAULT_TIMEOUT,
    DOMAIN,
    HA_USER_AGENT,
    MANUFACTURER,
    NO_IP_ERRORS,
    UPDATE_URL,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = {
    vol.Required(CONF_DOMAIN): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_USERNAME): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
}


class UpdateError(HomeAssistantError):
    """Base class for UpdateError HomeAssistantError."""


async def async_validate_no_ip(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Update No-IP.com."""
    no_ip_domain = user_input[CONF_DOMAIN]
    user = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]

    auth_str = base64.b64encode(f"{user}:{password}".encode())

    session = aiohttp_client.async_create_clientsession(hass)
    params = {"hostname": no_ip_domain}

    headers = {
        AUTHORIZATION: f"Basic {auth_str.decode('utf-8')}",
        USER_AGENT: HA_USER_AGENT,
    }

    try:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            resp = await session.get(UPDATE_URL, params=params, headers=headers)
            body = await resp.text()
            if body.startswith("good") or body.startswith("nochg"):
                ipAddress = body.split(" ")[1]
                return {"title": MANUFACTURER, CONF_IP_ADDRESS: ipAddress}

            raise UpdateError(NO_IP_ERRORS[body.strip()])
    except aiohttp.ClientError as error:
        _LOGGER.warning("Can't connect to No-IP.com API")
        raise aiohttp.ClientError from error

    except asyncio.TimeoutError as error:
        _LOGGER.warning("Timeout from No-IP.com API for domain: %s", no_ip_domain)
        raise aiohttp.ClientError from error


class NoIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for No-IP.com integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}

        result = None

        if user_input:
            try:
                result = await async_validate_no_ip(self.hass, user_input)
            except UpdateError as error:
                errors["base"] = error.args[0]
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            if result:
                return self.async_create_entry(
                    title=result["title"],
                    data={
                        CONF_DOMAIN: user_input[CONF_DOMAIN],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import No-IP.com config from configuration.yaml."""
        if import_data:
            self._async_abort_entries_match(
                {
                    CONF_DOMAIN: import_data[CONF_DOMAIN],
                    CONF_USERNAME: import_data[CONF_USERNAME],
                }
            )

            _LOGGER.debug(
                "Starting import of sensor from configuration.yaml - %s", import_data
            )
            # Process the imported configuration data further
            return await self.async_step_user(import_data)

        return self.async_abort(reason="No configuration to import.")
