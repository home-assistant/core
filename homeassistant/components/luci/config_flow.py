"""Config flow for the OpenWrt (luci) integration."""

from __future__ import annotations

import logging
from typing import Any

from openwrt_luci_rpc import OpenWrtRpc
from requests.exceptions import ConnectionError as RequestsConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .const import DEFAULT_SSL, DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class LuciConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenWrt (luci)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                router = await self.hass.async_add_executor_job(
                    _try_connect, user_input
                )
            except ConnectionError, RequestsConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if not router.is_logged_in():
                    errors["base"] = "invalid_auth"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_HOST],
                        data=user_input,
                    )

            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )


def _try_connect(user_input: dict[str, Any]) -> OpenWrtRpc:
    """Try to connect to the router."""
    return OpenWrtRpc(
        user_input[CONF_HOST],
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
        user_input.get(CONF_SSL, DEFAULT_SSL),
        user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
