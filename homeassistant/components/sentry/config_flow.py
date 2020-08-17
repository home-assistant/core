"""Config flow for sentry integration."""
import logging
from typing import Any, Dict, Optional

from sentry_sdk.utils import BadDsn, Dsn
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_DSN, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_DSN): str})


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Sentry config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a user config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}
        if user_input is not None:
            try:
                Dsn(user_input["dsn"])
            except BadDsn:
                errors["base"] = "bad_dsn"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Sentry", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
