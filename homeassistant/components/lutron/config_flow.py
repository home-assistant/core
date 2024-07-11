"""Config flow to configure the Lutron integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.error import HTTPError

from pylutron import Lutron
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LutronConfigFlow(ConfigFlow, domain=DOMAIN):
    """User prompt for Main Repeater configuration information."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step in the config flow."""

        # Check if a configuration entry already exists
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

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
