"""Config flow for Opower integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from opower import (
    CannotConnect,
    InvalidAuth,
    MfaChallenge,
    MfaHandlerBase,
    Opower,
    create_cookie_jar,
    get_supported_utility_names,
    select_utility,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import VolDictType

from .const import CONF_LOGIN_DATA, CONF_TOTP_SECRET, CONF_UTILITY, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_MFA_CODE = "mfa_code"
CONF_MFA_METHOD = "mfa_method"


async def _validate_login(
    hass: HomeAssistant,
    data: Mapping[str, Any],
) -> None:
    """Validate login data and raise exceptions on failure."""
    api = Opower(
        async_create_clientsession(hass, cookie_jar=create_cookie_jar()),
        data[CONF_UTILITY],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data.get(CONF_TOTP_SECRET),
        data.get(CONF_LOGIN_DATA),
    )
    await api.async_login()


class OpowerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Opower."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a new OpowerConfigFlow."""
        self._data: dict[str, Any] = {}
        self.mfa_handler: MfaHandlerBase | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (select utility)."""
        if user_input is not None:
            self._data[CONF_UTILITY] = user_input[CONF_UTILITY]
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_UTILITY): vol.In(get_supported_utility_names())}
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle credentials step."""
        errors: dict[str, str] = {}
        utility = select_utility(self._data[CONF_UTILITY])

        if user_input is not None:
            self._data.update(user_input)

            self._async_abort_entries_match(
                {
                    CONF_UTILITY: self._data[CONF_UTILITY],
                    CONF_USERNAME: self._data[CONF_USERNAME],
                }
            )

            try:
                await _validate_login(self.hass, self._data)
            except MfaChallenge as exc:
                self.mfa_handler = exc.handler
                return await self.async_step_mfa_options()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_opower_entry(self._data)

        schema_dict: VolDictType = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        if utility.accepts_totp_secret():
            schema_dict[vol.Optional(CONF_TOTP_SECRET)] = str

        return self.async_show_form(
            step_id="credentials",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema_dict), user_input
            ),
            errors=errors,
        )

    async def async_step_mfa_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MFA options step."""
        errors: dict[str, str] = {}
        assert self.mfa_handler is not None

        if user_input is not None:
            method = user_input[CONF_MFA_METHOD]
            try:
                await self.mfa_handler.async_select_mfa_option(method)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_mfa_code()

        mfa_options = await self.mfa_handler.async_get_mfa_options()
        if not mfa_options:
            return await self.async_step_mfa_code()
        return self.async_show_form(
            step_id="mfa_options",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_MFA_METHOD): vol.In(mfa_options)}),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_mfa_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MFA code submission step."""
        assert self.mfa_handler is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_MFA_CODE]
            try:
                login_data = await self.mfa_handler.async_submit_mfa_code(code)
            except InvalidAuth:
                errors["base"] = "invalid_mfa_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self._data[CONF_LOGIN_DATA] = login_data
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=self._data
                    )
                return self._async_create_opower_entry(self._data)

        return self.async_show_form(
            step_id="mfa_code",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_MFA_CODE): str}), user_input
            ),
            errors=errors,
        )

    @callback
    def _async_create_opower_entry(
        self, data: dict[str, Any], **kwargs: Any
    ) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=f"{data[CONF_UTILITY]} ({data[CONF_USERNAME]})",
            data=data,
            **kwargs,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        reauth_entry = self._get_reauth_entry()
        self._data = dict(reauth_entry.data)
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_NAME: reauth_entry.title},
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            self._data.update(user_input)
        try:
            await _validate_login(self.hass, self._data)
        except MfaChallenge as exc:
            self.mfa_handler = exc.handler
            return await self.async_step_mfa_options()
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_update_reload_and_abort(reauth_entry, data=self._data)

        utility = select_utility(self._data[CONF_UTILITY])
        schema_dict: VolDictType = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        if utility.accepts_totp_secret():
            schema_dict[vol.Optional(CONF_TOTP_SECRET)] = str

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema_dict), self._data
            ),
            errors=errors,
            description_placeholders={CONF_NAME: reauth_entry.title},
        )
