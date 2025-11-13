"""Config flow for the Signal Messenger v2 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_RECP_NR, CONF_SENDER_NR, CONF_SIGNAL_CLI_REST_API, DOMAIN
from .notify import get_api

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENDER_NR): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_SIGNAL_CLI_REST_API): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_RECP_NR): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="recipients-comma-separated",
            )
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = get_api(data)

    _LOGGER.debug("Validating connection to Signal CLI REST API")

    try:
        await hass.async_add_executor_job(api.about)
    except Exception as ex:
        raise CannotConnect from ex

    return {"title": data[CONF_SENDER_NR]}


class SignalNotificationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Signal Messenger v2 integration."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                _LOGGER.exception("Unexpected error encountered during connection")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id("identifier")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
