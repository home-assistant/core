"""Config flow to configure the Lutron integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.error import HTTPError

import voluptuous as vol
from pylutron import Lutron

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import CONF_DEFAULT_DIMMER_LEVEL, DEFAULT_DIMMER_LEVEL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LutronConfigFlow(ConfigFlow, domain=DOMAIN):
    """User prompt for Main Repeater configuration information."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step in the config flow."""
        errors = {}

        if user_input is not None:
            ip_address = user_input[CONF_HOST]

            main_repeater = Lutron(
                ip_address,
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
            )

            try:
                await self.hass.async_add_executor_job(main_repeater.load_xml_db)
            except HTTPError:
                _LOGGER.exception("Http error")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            else:
                guid = main_repeater.guid

                if len(guid) <= 10:
                    errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(guid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title="Lutron", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME, default="lutron"): str,
                    vol.Required(CONF_PASSWORD, default="integration"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for esphome."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEFAULT_DIMMER_LEVEL,
                    default=self.config_entry.options.get(
                        CONF_DEFAULT_DIMMER_LEVEL, DEFAULT_DIMMER_LEVEL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
