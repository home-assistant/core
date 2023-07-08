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
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DEFAULT_SCAN_INTERVAL,
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
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
        NumberSelectorConfig(
            min=10,
            max=9999,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="seconds",
        ),
    ),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): NumberSelector(
        NumberSelectorConfig(
            min=1,
            unit_of_measurement="minutes",
            mode=NumberSelectorMode.BOX,
        ),
    ),
}


class UpdateError(HomeAssistantError):
    """Base class for UpdateError HomeAssistantError."""


async def async_validate_no_ip(
    session: aiohttp.ClientSession, domain: str, auth_str: bytes, timeout: int
) -> dict[str, str]:
    """Update No-IP.com."""
    params = {"hostname": domain}

    headers = {
        AUTHORIZATION: f"Basic {auth_str.decode('utf-8')}",
        USER_AGENT: HA_USER_AGENT,
    }

    try:
        async with async_timeout.timeout(timeout):
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
        _LOGGER.warning("Timeout from No-IP.com API for domain: %s", domain)
        raise aiohttp.ClientError from error


class NoIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for No-IP.com integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NoIPOptionsFlowHandler:
        """Return Option handler."""
        return NoIPOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        result = None

        if user_input:
            no_ip_domain = user_input[CONF_DOMAIN]
            timeout = user_input[CONF_TIMEOUT]
            user = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            auth_str = base64.b64encode(f"{user}:{password}".encode())

            session = aiohttp_client.async_create_clientsession(self.hass)

            try:
                result = await async_validate_no_ip(
                    session, no_ip_domain, auth_str, timeout
                )
            except UpdateError as error:
                errors["base"] = error.args[0]
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            if result:
                return self.async_create_entry(
                    title=result["title"],
                    data={
                        CONF_DOMAIN: user_input[CONF_DOMAIN],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import No-IP.com config from configuration.yaml."""

        _LOGGER.debug(
            "Starting import of sensor from configuration.yaml - %s", import_data
        )
        if import_data:
            self._async_abort_entries_match({CONF_DOMAIN: import_data[CONF_DOMAIN]})
            # Process the imported configuration data further
            return await self.async_step_user(import_data)

        return self.async_abort(reason="No configuration to import.")


class NoIPOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle a option config flow for No-IP.com integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        options = self.options
        errors: dict[str, str] = {}
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TIMEOUT, default=options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="seconds",
                    ),
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        unit_of_measurement="minutes",
                        mode=NumberSelectorMode.BOX,
                    ),
                ),
            }
        )
        if user_input is not None:
            return self.async_create_entry(title=MANUFACTURER, data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors, last_step=True
        )
