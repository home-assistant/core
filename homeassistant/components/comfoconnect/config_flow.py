"""Config flow to configure the Comfoconnect integration."""
from __future__ import annotations

from typing import Any

from pycomfoconnect import Bridge
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    _LOGGER,
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_NAME_IMPORT,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)


class ComfoConnectFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Comfoconnect config flow."""

    VERSION = 1

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry."""
        import_config = import_config.get(DOMAIN, import_config)

        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == import_config[CONF_HOST]:
                _LOGGER.warning(
                    "YAML config for ComfoConnect bridge on %s has been imported. Please remove it from your configuration.YAML",
                    import_config[CONF_HOST],
                )
                return self.async_abort(reason="already_configured")

        # Enhance with defaults if necessary
        import_config[CONF_NAME] = import_config.get(CONF_NAME, DEFAULT_NAME)
        import_config[CONF_TOKEN] = import_config.get(CONF_TOKEN, DEFAULT_TOKEN)
        import_config[CONF_PIN] = import_config.get(CONF_PIN, DEFAULT_PIN)
        import_config[CONF_USER_AGENT] = import_config.get(
            CONF_USER_AGENT, DEFAULT_USER_AGENT
        )

        return await self.async_step_user(import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]
            token = user_input[CONF_TOKEN]
            user_agent = user_input[CONF_USER_AGENT]
            pin = user_input[CONF_PIN]

            self._async_abort_entries_match({CONF_HOST: host})

            # Run discovery on the configured ip
            bridges = Bridge.discover(host)
            if not bridges:
                errors["base"] = "cannot_connect"
                return await self._show_setup_form(errors)

            bridge = bridges[0]
            _LOGGER.info("Bridge found: %s (%s)", bridge.uuid.hex(), bridge.host)

            title = DEFAULT_NAME_IMPORT if self.source == SOURCE_IMPORT else name
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: host,
                    CONF_NAME: name,
                    CONF_TOKEN: token,
                    CONF_USER_AGENT: user_agent,
                    CONF_PIN: pin,
                },
            )

        return await self._show_setup_form(user_input)

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                    vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): vol.All(
                        str, vol.Length(min=32, max=32, msg="invalid token")
                    ),
                    vol.Optional(
                        CONF_USER_AGENT, default=DEFAULT_USER_AGENT
                    ): cv.string,
                    vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
                }
            ),
            errors=errors or {},
        )
