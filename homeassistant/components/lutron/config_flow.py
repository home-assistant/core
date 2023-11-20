"""Config flow to configure the Lutron integration."""
from __future__ import annotations

import logging
from urllib.error import HTTPError

from pylutron import Lutron
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LutronConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User prompt for Main Repeater configuration information."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """First step in the config flow."""
        errors = {}

        if user_input is not None:
            # Validate user input
            # user_input.get(CONF_USERNAME)
            # user_input.get(CONF_PASSWORD)
            ip_address = user_input(CONF_HOST)

            # Now that we have the data, check and see if we can connect and get a GUID
            main_repeater = Lutron(
                ip_address,
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
            )

            def _load_db() -> bool:
                main_repeater.load_xml_db()
                return True

            try:
                await self.hass.async_add_executor_job(_load_db)
                guid = main_repeater.guid
            except UnknownConnectError:
                errors["base"] = "config_errors"
            except HTTPError as ex:
                # In a future version we can get more specific with the HTTP code
                _LOGGER.debug("Exception Type: %s", type(ex).__name__)
                errors["base"] = "connect_error"

            if not errors:
                if len(guid) > 10:
                    _LOGGER.info("Main Repeater GUID: %s", main_repeater.guid)
                else:
                    errors["base"] = "missing_guid"

            # Check if a configuration entry with the same unique ID already exists
            if not errors:
                if self._async_current_entries():
                    return self.async_abort(reason="single_instance_allowed")

            if not errors:
                await self.async_set_unique_id(guid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title="Lutron", data=user_input)

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input) -> FlowResult:
        """Handle import."""
        return await self.async_step_user(user_input)


class UnknownConnectError(Exception):
    """Catch unknown connection error."""
