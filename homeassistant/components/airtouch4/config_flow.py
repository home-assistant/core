"""Config flow for AirTouch4."""
from airtouch4pyapi import AirTouch
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _validate_connection(hass: core.HomeAssistant, host):
    airtouch = AirTouch(host)
    await airtouch.UpdateInfo()

    if hasattr(airtouch, "error"):
        if isinstance(airtouch.error, Exception):
            raise airtouch.error
        raise ConnectionError()
    return bool(airtouch.GetGroups())


class AirtouchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Airtouch config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        host = user_input[CONF_HOST]

        try:
            result = await _validate_connection(self.hass, host)
            if not result:
                errors["base"] = "no_units"
        except (OSError, ConnectionError):
            errors["base"] = "cannot_connect"

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
