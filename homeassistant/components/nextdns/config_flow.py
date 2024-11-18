"""Adds config flow for NextDNS."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError, NextDns
from tenacity import RetryError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PROFILE_ID, DOMAIN

AUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


async def async_init_nextdns(hass: HomeAssistant, api_key: str) -> NextDns:
    """Check if credentials are valid."""
    websession = async_get_clientsession(hass)

    return await NextDns.create(websession, api_key)


class NextDnsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for NextDNS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.nextdns: NextDns
        self.api_key: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]
            try:
                self.nextdns = await async_init_nextdns(self.hass, self.api_key)
            except InvalidApiKeyError:
                errors["base"] = "invalid_api_key"
            except (ApiError, ClientConnectorError, RetryError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return await self.async_step_profiles()

        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the profiles step."""
        errors: dict[str, str] = {}

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await async_init_nextdns(self.hass, user_input[CONF_API_KEY])
            except InvalidApiKeyError:
                errors["base"] = "invalid_api_key"
            except (ApiError, ClientConnectorError, RetryError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )
