"""Config flow to configure the Proliphix integration."""

from __future__ import annotations

from typing import Any

from proliphix import PDP
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER


class ProliphixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Proliphix."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Check if already configured with this host
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            # Test connection to the thermostat
            try:
                pdp = PDP(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await self.hass.async_add_executor_job(pdp.update)
                title = await self.hass.async_add_executor_job(lambda: pdp.name)
            except requests.exceptions.RequestException:
                LOGGER.exception("Network error connecting to Proliphix thermostat")
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title or "Proliphix", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): TextSelector(
                        TextSelectorConfig(autocomplete="off")
                    ),
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(autocomplete="off")
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle YAML import."""
        # Check if already configured with this host
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        return self.async_create_entry(
            title="Proliphix",
            data={
                CONF_HOST: import_config[CONF_HOST],
                CONF_USERNAME: import_config[CONF_USERNAME],
                CONF_PASSWORD: import_config[CONF_PASSWORD],
            },
        )
