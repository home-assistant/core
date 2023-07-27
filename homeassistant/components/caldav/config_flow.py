"""Config flow to configure caldav."""
from __future__ import annotations

import logging

from caldav.lib.error import DAVError
import voluptuous as vol
from yarl import URL as yurl

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from . import async_caldav_connect
from .const import (
    CONF_CALENDARS,
    CONF_CUSTOM_CALENDARS,
    CONF_DAYS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        # pylint: disable=no-value-for-parameter
        vol.Required(CONF_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_URL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Optional(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
        vol.Optional(CONF_DAYS, default=1): cv.positive_int,
    }
)

_LOGGER = logging.getLogger(__name__)


class CaldavFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a caldav config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.user_input = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_URL: user_input[CONF_URL],
                }
            )

            try:
                await async_caldav_connect(self.hass, user_input)
                url = yurl(user_input[CONF_URL])
            except DAVError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{url.host} ({user_input[CONF_USERNAME]})",
                    data=user_input,
                    options={CONF_CALENDARS: [], CONF_CUSTOM_CALENDARS: []},
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)
