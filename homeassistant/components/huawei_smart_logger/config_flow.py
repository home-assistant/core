"""Config flow for HuaweiSmartLogger3000 integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from huawei_smart_logger.huawei_smart_logger import HuaweiSmartLogger3000API
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: core.HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """During configuration setup we will log in to validate credentials and server info."""
    _LOGGER.debug("In validate input")

    try:
        hsl = HuaweiSmartLogger3000API(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input[CONF_HOST]
        )
        await hsl.fetch_data()

    except aiohttp.ClientError as e:
        _LOGGER.error("Connection timed out to %s", user_input[CONF_HOST])
        raise CannotConnect from e

    return user_input


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

    _LOGGER.error("Cannot connect")


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

    _LOGGER.error("Invalid auth")


class HuaweiSmartLogger3000ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow definition."""

    VERSION = 1

    _LOGGER.debug("In Config flow class")

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            try:
                await validate_input(self.hass, user_input=user_input)
            except Exception:  # pylint: disable=broad-except
                # LOGGER.exception("Unexpected exception")
                _LOGGER.error(
                    "An error during setup has occurred please verify credentials and host information"
                )
                errors["base"] = "unknown"

            self._async_abort_entries_match({CONF_HOST: CONF_HOST})

            if not (errors):
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=self._config
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=user_input.get(CONF_PASSWORD, ""),
                    ): str,
                }
            ),
            errors=errors,
        )
