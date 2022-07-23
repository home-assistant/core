"""Config flow for Steam integration."""
from __future__ import annotations

from collections.abc import Mapping
import operator
from typing import Any

from steam.api import HTTPError, HTTPTimeoutError, key
from steam.user import ProfileNotFoundError, friend_list, profile, profile_batch
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    PLACEHOLDERS,
)


def validate_input(user_input: dict[str, str]) -> profile:
    """Handle common flow input validation."""
    key.set(user_input[CONF_API_KEY])
    user = profile(user_input[CONF_ACCOUNT])
    # Property is blocking. So we call it here
    user.persona  # pylint:disable=pointless-statement
    return user


class SteamFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Steam."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SteamOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is None and self.entry:
            user_input = {CONF_ACCOUNT: self.entry.data[CONF_ACCOUNT]}
        elif user_input is not None:
            try:
                usr = await self.hass.async_add_executor_job(validate_input, user_input)
            except ProfileNotFoundError:
                errors["base"] = "invalid_account"
            except (HTTPError, HTTPTimeoutError) as ex:
                errors["base"] = "cannot_connect"
                if "403" in str(ex):
                    errors["base"] = "invalid_auth"
            except Exception as ex:  # pylint:disable=broad-except
                LOGGER.exception("Unknown exception: %s", ex)
                errors["base"] = "unknown"
            if not errors:
                entry = await self.async_set_unique_id(user_input[CONF_ACCOUNT])
                if entry and self.source == config_entries.SOURCE_REAUTH:
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                    options={CONF_ACCOUNTS: {user_input[CONF_ACCOUNT]: usr.persona}},
                )
        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY) or ""
                    ): str,
                    vol.Required(
                        CONF_ACCOUNT, default=user_input.get(CONF_ACCOUNT) or ""
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="reauth_confirm", description_placeholders=PLACEHOLDERS
        )


class SteamOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Steam client options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry
        self.options = dict(entry.options)

    async def async_step_init(
        self, user_input: dict[str, dict[str, str]] | None = None
    ) -> FlowResult:
        """Manage Steam options."""
        if user_input is not None:
            channel_data = {
                CONF_ACCOUNTS: {
                    _id: name
                    for _id, name in self.options[CONF_ACCOUNTS].items()
                    if _id in user_input[CONF_ACCOUNTS]
                }
            }
            reg = dr.async_get(self.hass)
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            for _id in self.options[CONF_ACCOUNTS].keys():
                if _id not in user_input[CONF_ACCOUNTS]:
                    if device := reg.async_get_device({(DOMAIN, _id)}):
                        reg.async_remove_device(device.id)
            return self.async_create_entry(title="", data=channel_data)
        error = None

        accs = await self.hass.async_add_executor_job(self.get_accounts)
        if not (users := {str(user.id64): user.persona for user in accs}):
            error = {"base": "problem"}

        users = users | self.options[CONF_ACCOUNTS]
        _options = dict(sorted(users.items(), key=operator.itemgetter(1)))

        options = {
            vol.Required(
                CONF_ACCOUNTS,
                default=set(self.options[CONF_ACCOUNTS]),
            ): cv.multi_select(_options),
        }
        self.options[CONF_ACCOUNTS] = _options
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=error
        )

    def get_accounts(self) -> list[profile]:
        """Get accounts."""
        try:
            friends = friend_list(self.entry.data[CONF_ACCOUNT])
            profiles = []
            _profile: profile
            for _profile in profile_batch([friend.steamid for friend in friends]):
                # Property is blocking. So we call it here
                _profile.persona  # pylint:disable=pointless-statement
                profiles.append(_profile)
            return profiles
        except HTTPError:
            return []
