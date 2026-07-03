"""Adds config flow for NextDNS."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError, NextDns
from tenacity import RetryError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PROFILE_ID, DOMAIN, SUBENTRY_TYPE_PROFILE

AUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})

_LOGGER = logging.getLogger(__name__)


async def async_init_nextdns(hass: HomeAssistant, api_key: str) -> NextDns:
    """Check if credentials and profile_id are valid."""
    websession = async_get_clientsession(hass)

    return await NextDns.create(websession, api_key)


async def async_validate_new_api_key(
    hass: HomeAssistant, user_input: dict[str, Any], profile_ids: list[str]
) -> dict[str, str]:
    """Validate the new API key during reconfiguration or reauth."""
    errors: dict[str, str] = {}

    try:
        nextdns = await async_init_nextdns(hass, user_input[CONF_API_KEY])
    except InvalidApiKeyError:
        errors["base"] = "invalid_api_key"
    except ApiError, ClientConnectorError, RetryError, TimeoutError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        for profile_id in profile_ids:
            if not any(profile.id == profile_id for profile in nextdns.profiles):
                errors["base"] = "profile_not_available"
                break

    return errors


class NextDnsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for NextDNS."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.nextdns: NextDns
        self.api_key: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.api_key = user_input[CONF_API_KEY]

            self._async_abort_entries_match({CONF_API_KEY: self.api_key})

            try:
                self.nextdns = await async_init_nextdns(self.hass, self.api_key)
            except InvalidApiKeyError:
                errors["base"] = "invalid_api_key"
            except ApiError, ClientConnectorError, RetryError, TimeoutError:
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

            return self.async_create_entry(
                title="NextDNS",
                data={CONF_API_KEY: self.api_key},
                subentries=[
                    {
                        "subentry_type": SUBENTRY_TYPE_PROFILE,
                        "data": {CONF_PROFILE_ID: profile_id},
                        "title": profile_name,
                        "unique_id": profile_id,
                    },
                ],
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
            profile_ids = [
                subentry.data[CONF_PROFILE_ID] for subentry in entry.subentries.values()
            ]
            errors = await async_validate_new_api_key(
                self.hass, user_input, profile_ids
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
            profile_ids = [
                subentry.data[CONF_PROFILE_ID] for subentry in entry.subentries.values()
            ]
            errors = await async_validate_new_api_key(
                self.hass, user_input, profile_ids
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

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_PROFILE: ProfileSubentryFlowHandler}


class ProfileSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for profile."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.nextdns: NextDns

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Handle the profile step."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}

        self.nextdns = entry.runtime_data.client

        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            profile_id = self.nextdns.get_profile_id(profile_name)

            if any(
                subentry.unique_id == profile_id
                for subentry in entry.subentries.values()
            ):
                errors["base"] = "already_configured"
            else:
                return self.async_create_entry(
                    title=profile_name,
                    data={CONF_PROFILE_ID: profile_id},
                    unique_id=profile_id,
                )

        # Filter out already configured profiles
        configured_profiles = {
            subentry.data[CONF_PROFILE_ID] for subentry in entry.subentries.values()
        }
        available_profiles = [
            profile.name
            for profile in self.nextdns.profiles
            if profile.id not in configured_profiles
        ]

        if not available_profiles:
            return self.async_abort(reason="all_profiles_configured")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PROFILE_NAME): vol.In(available_profiles)}
            ),
            errors=errors,
        )
