"""Config flow for Vivotek IP cameras integration."""

import logging
from typing import Any

from libpyvivotek.vivotek import SECURITY_LEVELS, VivotekCameraError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import VivotekConfigEntry, async_build_and_test_cam_client
from .camera import DEFAULT_NAME, DEFAULT_STREAM_SOURCE
from .const import CONF_FRAMERATE, CONF_SECURITY_LEVEL, CONF_STREAM_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_PLACEHOLDERS = {
    "doc_url": "https://www.home-assistant.io/integrations/vivotek/"
}

CONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT, default=80): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Required(CONF_SECURITY_LEVEL): SelectSelector(
            SelectSelectorConfig(
                options=list(SECURITY_LEVELS.keys()),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="security_level",
                sort=True,
            ),
        ),
        vol.Required(
            CONF_STREAM_PATH,
            default=DEFAULT_STREAM_SOURCE,
        ): cv.string,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FRAMERATE, default=2): cv.positive_int,
    }
)


class OptionsFlowHandler(OptionsFlow):
    """Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


class VivotekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vivotek IP cameras."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: VivotekConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()

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
                    title=DEFAULT_NAME,
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

    async def async_step_import(
        self, import_data: (dict[str, Any])
    ) -> ConfigFlowResult:
        """Import a Yaml config."""
        self._async_abort_entries_match({CONF_IP_ADDRESS: import_data[CONF_IP_ADDRESS]})

        _LOGGER.debug("Importing Vivotek camera with data: %s", import_data)
        _input = {
            CONF_IP_ADDRESS: import_data.get("ip_address"),
            CONF_USERNAME: import_data.get("username"),
            CONF_PASSWORD: import_data.get("password"),
            CONF_AUTHENTICATION: import_data.get("authentication"),
            CONF_SSL: import_data.get("ssl"),
            CONF_VERIFY_SSL: import_data.get("verify_ssl"),
            CONF_FRAMERATE: import_data.get("framerate"),
            CONF_SECURITY_LEVEL: import_data.get("security_level"),
            CONF_STREAM_PATH: import_data.get("stream_path"),
            CONF_PORT: (import_data.get("ssl") and 443) or 80,
        }
        user_input = {k: v for k, v in _input.items() if v is not None}
        try:
            await async_build_and_test_cam_client(self.hass, user_input)
        except VivotekCameraError as err:
            raise ConfigEntryError("Failed to connect to camera") from err

        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

    async def _async_test_config(self, user_input: dict[str, Any]) -> None:
        """Test if the provided configuration is valid."""
        await async_build_and_test_cam_client(self.hass, user_input)
