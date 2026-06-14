"""Config flow for Midea ccm15 AC Controller integration."""

import logging
from typing import Any

from ccm15 import CCM15Device
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)
            ): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, 80)): cv.port,
            vol.Optional(
                CONF_MIN_TEMP,
                default=defaults.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=40)),
            vol.Optional(
                CONF_MAX_TEMP,
                default=defaults.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=40)),
        }
    )


def _validate_temps(user_input: dict[str, Any]) -> str | None:
    if user_input[CONF_MIN_TEMP] >= user_input[CONF_MAX_TEMP]:
        return "invalid_temp_range"
    return None


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
            if (err := _validate_temps(user_input)) is not None:
                errors["base"] = err
            else:
                ccm15 = CCM15Device(
                    user_input[CONF_HOST], user_input[CONF_PORT], DEFAULT_TIMEOUT
                )
                try:
                    if not await ccm15.async_test_connection():
                        errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=_build_schema(user_input), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow editing host, port and temperature limits."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # _async_abort_entries_match has no built-in way to exclude the
            # entry being reconfigured, so do the host/port collision check
            # manually here. The user step uses _async_abort_entries_match.
            for other in self._async_current_entries(include_ignore=False):
                if (
                    other.entry_id != entry.entry_id
                    and other.data.get(CONF_HOST) == user_input[CONF_HOST]
                    and other.data.get(CONF_PORT) == user_input[CONF_PORT]
                ):
                    return self.async_abort(reason="already_configured")

            if (err := _validate_temps(user_input)) is not None:
                errors["base"] = err
            else:
                ccm15 = CCM15Device(
                    user_input[CONF_HOST], user_input[CONF_PORT], DEFAULT_TIMEOUT
                )
                try:
                    if not await ccm15.async_test_connection():
                        errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

            if not errors:
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(user_input or dict(entry.data)),
            errors=errors,
        )
