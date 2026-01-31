"""Adds config flow for NextDNS."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError, NextDns
from tenacity import RetryError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PROFILE_ID, DOMAIN

AUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})

_LOGGER = logging.getLogger(__name__)


async def async_init_nextdns(
    hass: HomeAssistant, api_key: str, profile_id: str | None = None
) -> NextDns:
    """Check if credentials and profile_id are valid."""
    websession = async_get_clientsession(hass)

    nextdns = await NextDns.create(websession, api_key)

    if profile_id:
        if not any(profile.id == profile_id for profile in nextdns.profiles):
            raise ProfileNotAvailable

    return nextdns


async def async_validate_new_api_key(
    hass: HomeAssistant, user_input: dict[str, Any], profile_id: str
) -> dict[str, str]:
    """Validate the new API key during reconfiguration or reauth."""
    errors: dict[str, str] = {}

    try:
        await async_init_nextdns(hass, user_input[CONF_API_KEY], profile_id)
    except InvalidApiKeyError:
        errors["base"] = "invalid_api_key"
    except (ApiError, ClientConnectorError, RetryError, TimeoutError):
        errors["base"] = "cannot_connect"
    except ProfileNotAvailable:
        errors["base"] = "profile_not_available"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return errors


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
            except Exception:
                _LOGGER.exception("Unexpected exception")
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
        entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await async_validate_new_api_key(
                self.hass, user_input, entry.data[CONF_PROFILE_ID]
            )
            if errors.get("base") == "profile_not_available":
                return self.async_abort(reason="profile_not_available")

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            errors = await async_validate_new_api_key(
                self.hass, user_input, entry.data[CONF_PROFILE_ID]
            )
            if errors.get("base") == "profile_not_available":
                return self.async_abort(reason="profile_not_available")

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )


class ProfileNotAvailable(HomeAssistantError):
    """Error to indicate that the profile is not available after reconfig/reauth."""
