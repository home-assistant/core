"""Adds config flow for NextDNS."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError, NextDns
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PROFILE_ID, CONF_PROFILE_NAME, DOMAIN


class NextDnsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for NextDNS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.nextdns: NextDns | None = None
        self.api_key: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        websession = async_get_clientsession(self.hass)

        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            try:
                async with asyncio.timeout(10):
                    self.nextdns = await NextDns.create(
                        websession, user_input[CONF_API_KEY]
                    )
            except InvalidApiKeyError:
                errors["base"] = "invalid_api_key"
            except (ApiError, ClientConnectorError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return await self.async_step_profiles()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the profiles step."""
        errors: dict[str, str] = {}

        assert self.nextdns is not None

        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            profile_id = self.nextdns.get_profile_id(profile_name)

            await self.async_set_unique_id(profile_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=profile_name,
                data={CONF_PROFILE_ID: profile_id, CONF_API_KEY: self.api_key},
            )

        return self.async_show_form(
            step_id="profiles",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROFILE_NAME): vol.In(
                        [profile.name for profile in self.nextdns.profiles]
                    )
                }
            ),
            errors=errors,
        )
