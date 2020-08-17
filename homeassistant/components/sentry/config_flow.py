"""Config flow for sentry integration."""
import logging
from typing import Any, Dict, Optional

from sentry_sdk.utils import BadDsn, Dsn
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (  # pylint: disable=unused-import
    CONF_DSN,
    CONF_ENVIRONMENT,
    CONF_EVENT_CUSTOM_COMPONENTS,
    CONF_EVENT_HANDLED,
    CONF_EVENT_THIRD_PARTY_PACKAGES,
    CONF_LOGGING_EVENT_LEVEL,
    CONF_LOGGING_LEVEL,
    DEFAULT_LOGGING_EVENT_LEVEL,
    DEFAULT_LOGGING_LEVEL,
    DOMAIN,
    LOGGING_LEVELS,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_DSN): str})


class SentryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Sentry config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SentryOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a user config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

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


class SentryOptionsFlow(config_entries.OptionsFlow):
    """Handle Sentry options."""

    def __init__(self, config_entry):
        """Initialize Sentry options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manage Sentry options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LOGGING_EVENT_LEVEL,
                        default=self.config_entry.options.get(
                            CONF_LOGGING_EVENT_LEVEL, DEFAULT_LOGGING_EVENT_LEVEL
                        ),
                    ): vol.In(LOGGING_LEVELS),
                    vol.Optional(
                        CONF_LOGGING_LEVEL,
                        default=self.config_entry.options.get(
                            CONF_LOGGING_LEVEL, DEFAULT_LOGGING_LEVEL
                        ),
                    ): vol.In(LOGGING_LEVELS),
                    vol.Optional(
                        CONF_ENVIRONMENT,
                        default=self.config_entry.options.get(CONF_ENVIRONMENT),
                    ): str,
                    vol.Optional(
                        CONF_EVENT_HANDLED,
                        default=self.config_entry.options.get(
                            CONF_EVENT_HANDLED, False
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_EVENT_CUSTOM_COMPONENTS,
                        default=self.config_entry.options.get(
                            CONF_EVENT_CUSTOM_COMPONENTS, False
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_EVENT_THIRD_PARTY_PACKAGES,
                        default=self.config_entry.options.get(
                            CONF_EVENT_THIRD_PARTY_PACKAGES, False
                        ),
                    ): bool,
                }
            ),
        )
