"""Config flow for NZBGet."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import SectionConfig, section

from .const import (
    CONF_MORE_OPTIONS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import NZBGetAPI, NZBGetAPIException

_LOGGER = logging.getLogger(__name__)


def _validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    nzbget_api = NZBGetAPI(
        host=data[CONF_HOST],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        secure=data[CONF_SSL],
        verify_certificate=data[CONF_VERIFY_SSL],
        port=data[CONF_PORT],
    )

    nzbget_api.version()


class NZBGetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NZBGet."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            more_options = user_input.pop(CONF_MORE_OPTIONS, {})
            user_input[CONF_VERIFY_SSL] = more_options.get(
                CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
            )

            try:
                await self.hass.async_add_executor_job(_validate_input, user_input)
            except NZBGetAPIException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                # Name field is no longer allowed in config flow schemas
                # pylint: disable-next=home-assistant-config-flow-name-field
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                vol.Required(CONF_MORE_OPTIONS): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                            ): bool,
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {},
        )
