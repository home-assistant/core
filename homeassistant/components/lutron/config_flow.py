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

        # Check if a configuration entry with the same unique ID already exists
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            # Validate user input
            ip_address = user_input[CONF_HOST]

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
            except HTTPError as ex:
                # In a future version we can get more specific with the HTTP code
                _LOGGER.debug("Exception Type: %s", type(ex).__name__)
                errors["base"] = "connect_error"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.debug("Exception Type: %s", type(ex).__name__)
                errors["base"] = "config_errors"
            else:
                guid = main_repeater.guid
                if len(guid) > 10:
                    _LOGGER.info("Main Repeater GUID: %s", main_repeater.guid)
                else:
                    errors["base"] = "missing_guid"

                await self.async_set_unique_id(guid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title="Lutron", data=user_input)

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default="lutron"): str,
                    vol.Required(CONF_PASSWORD, default="integration"): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config) -> FlowResult:
        """Attempt to import the existing configuration.

        We will try to validate any legacy yaml first
        If that works then we create the entry from that data and save
        the user the work to create the new entry.
        If that fails, then we prompt the user to supply the data.
        """

        errors = {}
        main_repeater = Lutron(
            import_config[CONF_HOST],
            import_config[CONF_USERNAME],
            import_config[CONF_PASSWORD],
        )

        def _load_db(self, config: dict[str, str]) -> str | None:
            """Validate input data and return any error."""
            try:
                main_repeater.load_xml_db()
            except Exception as ex:  # pylint: disable=broad-except
                return str(ex)

            return None

        try:
            await self.hass.async_add_executor_job(_load_db)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Unable to import configuration.yaml configuration: %s", ex)
            _LOGGER.error(
                "You will now be directed to enter the configuration"
                "Please remember to remove the yaml from "
                "your configuration.yaml as it is no longer valid"
            )
            return await self.async_step_user(import_config)

        guid = main_repeater.guid

        if len(guid) > 10:
            _LOGGER.info("Main Repeater GUID: %s", main_repeater.guid)
        else:
            errors["base"] = "missing_guid"
            return self.async_abort(
                reason="missing_guid",
                description_placeholders={"error": errors["base"]},
            )

        await self.async_set_unique_id(guid)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Lutron", data=import_config)
