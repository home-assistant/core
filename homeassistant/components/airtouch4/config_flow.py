"""Config flow for AirTouch4."""
import logging

from airtouch4pyapi import AirTouch, AirTouchStatus, AirTouchVersion
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import selector

from .const import DOMAIN

DATA_SCHEMA = {vol.Required(CONF_HOST): str}

_LOGGER = logging.getLogger(__name__)


class AirtouchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Airtouch config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is None:
            if self.show_advanced_options:
                DATA_SCHEMA[vol.Optional(CONF_PORT, default="")] = str
                DATA_SCHEMA[vol.Optional("airtouch_version")] = selector(
                    {
                        "select": {
                            "options": ["Auto", "4", "5"],
                        }
                    }
                )

            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(DATA_SCHEMA)
            )

        errors = {}

        host = user_input[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})
        if CONF_PORT in user_input and user_input[CONF_PORT] != "":
            _LOGGER.debug("Performing advanced airtouch config with port and version")
            port = user_input[CONF_PORT]
            if user_input["airtouch_version"] == "4":
                version = AirTouchVersion.AIRTOUCH4
            if user_input["airtouch_version"] == "5":
                version = AirTouchVersion.AIRTOUCH5
            airtouch = AirTouch(host, version, port)
        else:
            _LOGGER.debug("Performing standard airtouch config with just host")
            airtouch = AirTouch(host)

        await airtouch.UpdateInfo()
        airtouch_status = airtouch.Status
        airtouch_has_groups = bool(
            airtouch.Status == AirTouchStatus.OK and airtouch.GetGroups()
        )

        if airtouch_status != AirTouchStatus.OK:
            errors["base"] = "cannot_connect"
        elif not airtouch_has_groups:
            errors["base"] = "no_units"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
            },
        )
