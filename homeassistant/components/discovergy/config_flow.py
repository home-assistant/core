"""Config flow for Discovergy integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pydiscovergy import Discovergy
from pydiscovergy.authentication import BasicAuth
import pydiscovergy.error as discovergyError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_EMAIL,
        ): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        vol.Required(
            CONF_PASSWORD,
        ): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class DiscovergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discovergy."""

    VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        return await self.async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth step."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate user input and create config entry."""
        errors = {}

        if user_input:
            try:
                await Discovergy(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    httpx_client=get_async_client(self.hass),
                    authentication=BasicAuth(),
                ).meters()
            except (discovergyError.HTTPError, discovergyError.DiscovergyClientError):
                errors["base"] = "cannot_connect"
            except discovergyError.InvalidLogin:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error occurred while getting meters")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()

                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        entry=self._get_reauth_entry(),
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        entry=self._get_reconfigure_entry(),
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        suggested_values = None
        if self.source == SOURCE_REAUTH:
            suggested_values = self._get_reauth_entry().data
        if self.source == SOURCE_RECONFIGURE:
            suggested_values = self._get_reconfigure_entry().data

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA,
                suggested_values if suggested_values else user_input,
            ),
            errors=errors,
        )
