"""Config flow for PJLink integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import CONF_ENCODING, DEFAULT_ENCODING, DEFAULT_PORT, DOMAIN

TITLE = "PJLink"


class PJLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for PJLink."""

    def __init__(self) -> None:
        """Initialize config flow."""
        self.host: str | None = None
        self.port: int | None = None

    def _show_setup_form(self, step_id):
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
                    vol.Optional(CONF_PASSWORD): cv.string,
                }
            ),
        )

    # Can we can identify PJLink devices with dhcp or something else?
    # During authentication the library checks that we are talking to a PJLink device
    # https://github.com/benoitlouy/pypjlink/blob/1932aaf7c18113e6281927f4ee2d30c6b8593639/pypjlink/projector.py#L80-L85

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""

        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self._show_setup_form(step_id="user")

        return self.async_create_entry(
            title=TITLE,
            data=user_input,
        )
