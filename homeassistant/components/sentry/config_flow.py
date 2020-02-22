"""Config flow for sentry integration."""
import logging

from sentry_sdk.utils import BadDsn, Dsn
import voluptuous as vol

from homeassistant import config_entries, core

from .const import CONF_DSN, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_DSN): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the DSN input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # validate the dsn
    Dsn(data["dsn"])

    return {"title": "Sentry"}


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Sentry config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a user config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except BadDsn:
                errors["base"] = "bad_dsn"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)
