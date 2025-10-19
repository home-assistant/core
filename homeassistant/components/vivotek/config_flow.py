"""Config flow for Vivotek IP cameras integration."""

import logging
from types import MappingProxyType
from typing import Any

from libpyvivotek.vivotek import VivotekCameraError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.helpers import config_validation as cv

from .camera import (
    DEFAULT_NAME,
    DEFAULT_SECURITY_LEVEL,
    DEFAULT_STREAM_SOURCE,
    async_test_config,
)
from .const import CONF_FRAMERATE, CONF_SECURITY_LEVEL, CONF_STREAM_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULTS = {
    CONF_NAME: DEFAULT_NAME,
    CONF_PORT: 80,
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_FRAMERATE: 2,
    CONF_SECURITY_LEVEL: DEFAULT_SECURITY_LEVEL,
    CONF_STREAM_PATH: DEFAULT_STREAM_SOURCE,
}

DESCRIPTION_PLACEHOLDERS = {
    "doc_url": "https://www.home-assistant.io/integrations/vivotek/"
}


class VivotekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vivotek IP cameras."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_input: dict[str, Any] | None = None
        self._cam: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._user_input = user_input

            try:
                await self._async_test_config()
            except VivotekCameraError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_input_schema(user_input),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._user_input = user_input

            try:
                await self._async_test_config()
            except VivotekCameraError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        data = user_input or self._get_reconfigure_entry().data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._user_input_schema(data),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    def _user_input_schema(
        self, user_input: dict[str, Any] | MappingProxyType[str, Any] | None
    ) -> vol.Schema:
        """Return the input schema with defaults from existing user input."""
        data = user_input or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=data.get(CONF_NAME, CONF_DEFAULTS[CONF_NAME])
                ): cv.string,
                vol.Required(
                    CONF_IP_ADDRESS, default=data.get(CONF_IP_ADDRESS, "")
                ): cv.string,
                vol.Required(
                    CONF_PORT, default=data.get(CONF_PORT, CONF_DEFAULTS[CONF_PORT])
                ): cv.port,
                vol.Required(
                    CONF_USERNAME, default=data.get(CONF_USERNAME, "")
                ): cv.string,
                vol.Required(
                    CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")
                ): cv.string,
                vol.Required(
                    CONF_AUTHENTICATION,
                    default=data.get(
                        CONF_AUTHENTICATION, CONF_DEFAULTS[CONF_AUTHENTICATION]
                    ),
                ): vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
                vol.Required(
                    CONF_SSL, default=data.get(CONF_SSL, CONF_DEFAULTS[CONF_SSL])
                ): cv.boolean,
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=data.get(CONF_VERIFY_SSL, CONF_DEFAULTS[CONF_VERIFY_SSL]),
                ): cv.boolean,
                vol.Required(
                    CONF_FRAMERATE,
                    default=data.get(CONF_FRAMERATE, CONF_DEFAULTS[CONF_FRAMERATE]),
                ): cv.positive_int,
                vol.Required(
                    CONF_SECURITY_LEVEL,
                    default=data.get(
                        CONF_SECURITY_LEVEL, CONF_DEFAULTS[CONF_SECURITY_LEVEL]
                    ),
                ): cv.string,
                vol.Required(
                    CONF_STREAM_PATH,
                    default=data.get(CONF_STREAM_PATH, CONF_DEFAULTS[CONF_STREAM_PATH]),
                ): cv.string,
            }
        )

    async def _async_test_config(self) -> None:
        """Test if the provided configuration is valid."""
        user_input = self._user_input
        assert user_input is not None
        await async_test_config(self.hass, user_input)
