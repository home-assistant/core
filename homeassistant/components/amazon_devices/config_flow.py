"""Config flow for Amazon Devices integration."""

from __future__ import annotations

import logging
from typing import Any

from aioamazondevices import AmazonEchoApi, CannotAuthenticate, CannotConnect
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import CountrySelector

from .const import CONF_LOGIN_DATA, DEFAULT_COUNTRY, DOMAIN

_LOGGER = logging.getLogger(__package__)


class AmazonDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amazon Devices."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input:
            client = AmazonEchoApi(
                user_input[CONF_COUNTRY],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                data = await client.login_mode_interactive(user_input[CONF_CODE])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(data["customer_info"]["user_id"])
                self._abort_if_unique_id_configured()
                user_input.pop(CONF_CODE)
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input | {CONF_LOGIN_DATA: data},
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COUNTRY, default=DEFAULT_COUNTRY
                    ): CountrySelector(),
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_CODE): cv.positive_int,
                }
            ),
        )
