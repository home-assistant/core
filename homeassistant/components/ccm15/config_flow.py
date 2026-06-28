"""Config flow for Midea ccm15 AC Controller integration."""

from collections.abc import Mapping
import logging
from typing import Any

from ccm15 import CCM15Device
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_PASSWORD, default=""): _PASSWORD_SELECTOR,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PASSWORD, default=""): _PASSWORD_SELECTOR,
    }
)


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop the password key when the user left it blank."""
    if not user_input.get(CONF_PASSWORD):
        return {k: v for k, v in user_input.items() if k != CONF_PASSWORD}
    return user_input


class CCM15ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea ccm15 AC Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            ccm15 = CCM15Device(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                DEFAULT_TIMEOUT,
                client=get_async_client(self.hass),
                password=user_input.get(CONF_PASSWORD) or None,
            )
            try:
                if not await ccm15.async_test_connection():
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=_clean(user_input)
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Triggered by the coordinator when the controller rejects the password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt the user for a new password and re-test against the controller."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            ccm15 = CCM15Device(
                entry.data[CONF_HOST],
                entry.data[CONF_PORT],
                DEFAULT_TIMEOUT,
                client=get_async_client(self.hass),
                password=user_input.get(CONF_PASSWORD) or None,
            )
            try:
                # The controller only enforces the password on writes, so
                # this probe just confirms reachability — a wrong password
                # will resurface on the next set_state and re-trigger reauth.
                if not await ccm15.async_test_connection():
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                merged = {**entry.data}
                if user_input.get(CONF_PASSWORD):
                    merged[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                else:
                    merged.pop(CONF_PASSWORD, None)
                return self.async_update_reload_and_abort(entry, data=merged)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
