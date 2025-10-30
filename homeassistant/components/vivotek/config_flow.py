"""Config flow for Vivotek IP cameras integration."""

import logging
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

from . import async_build_and_test_cam_client
from .camera import DEFAULT_NAME, DEFAULT_SECURITY_LEVEL, DEFAULT_STREAM_SOURCE
from .const import CONF_FRAMERATE, CONF_SECURITY_LEVEL, CONF_STREAM_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_PLACEHOLDERS = {
    "doc_url": "https://www.home-assistant.io/integrations/vivotek/"
}

CONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT, default=80): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Required(CONF_FRAMERATE, default=2): cv.positive_int,
        vol.Required(CONF_SECURITY_LEVEL, default=DEFAULT_SECURITY_LEVEL): cv.string,
        vol.Required(
            CONF_STREAM_PATH,
            default=DEFAULT_STREAM_SOURCE,
        ): cv.string,
    }
)


class VivotekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vivotek IP cameras."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._async_test_config(user_input)
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
            data_schema=self.add_suggested_values_to_schema(
                CONF_SCHEMA, user_input or {}
            ),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._async_test_config(user_input)
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

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONF_SCHEMA, self._get_reconfigure_entry().data
            ),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )

    async def async_step_import(
        self, import_data: (dict[str, Any])
    ) -> ConfigFlowResult:
        """Import a Yaml config."""
        self._async_abort_entries_match({CONF_IP_ADDRESS: import_data[CONF_IP_ADDRESS]})

        _LOGGER.debug("Importing Vivotek camera with data: %s", import_data)
        user_input = {}
        if "ip_address" in import_data:
            user_input[CONF_IP_ADDRESS] = import_data["ip_address"]
        if "name" in import_data:
            user_input[CONF_NAME] = import_data["name"]
        if "username" in import_data:
            user_input[CONF_USERNAME] = import_data["username"]
        if "password" in import_data:
            user_input[CONF_PASSWORD] = import_data["password"]
        if "authentication" in import_data:
            user_input[CONF_AUTHENTICATION] = import_data["authentication"]
        if "ssl" in import_data:
            user_input[CONF_SSL] = import_data["ssl"]
        if "verify_ssl" in import_data:
            user_input[CONF_VERIFY_SSL] = import_data["verify_ssl"]
        if "framerate" in import_data:
            user_input[CONF_FRAMERATE] = import_data["framerate"]
        if "security_level" in import_data:
            user_input[CONF_SECURITY_LEVEL] = import_data["security_level"]
        if "stream_path" in import_data:
            user_input[CONF_STREAM_PATH] = import_data["stream_path"]

        user_input[CONF_PORT] = (user_input[CONF_SSL] and 443) or 80
        title = user_input.get(CONF_NAME, DOMAIN)
        return self.async_create_entry(title=title, data=user_input)

    async def _async_test_config(self, user_input: dict[str, Any]) -> None:
        """Test if the provided configuration is valid."""
        assert user_input is not None
        await async_build_and_test_cam_client(self.hass, user_input)
