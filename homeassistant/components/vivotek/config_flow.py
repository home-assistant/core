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
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import VivotekConfigEntry, async_build_and_test_cam_client, build_cam_client
from .camera import (
    DEFAULT_FRAMERATE,
    DEFAULT_NAME,
    DEFAULT_STREAM_SOURCE,
    INTEGRATION_TITLE,
)
from .const import (
    CONF_FRAMERATE,
    CONF_SECURITY_LEVEL,
    CONF_STREAM_PATH,
    DOMAIN,
    ISSUE_DEPRECATED_YAML,
)

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
        vol.Required(CONF_FRAMERATE, default=DEFAULT_FRAMERATE): cv.positive_int,
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
                cam_client = build_cam_client(user_input)
                mac_address = await self.hass.async_add_executor_job(cam_client.get_mac)
            except VivotekCameraError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during camera connection test")
                errors["base"] = "unknown"
            else:
                # prevent duplicates
                await self.async_set_unique_id(format_mac(mac_address))
                self._abort_if_unique_id_configured()

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

        port = (import_data.get(CONF_SSL) and 443) or 80
        import_data |= {CONF_PORT: port}
        try:
            config_flow_result: ConfigFlowResult = await self.async_step_user(
                import_data
            )
        except AbortFlow:
            # this happens if the config entry is already imported
            async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_DEPRECATED_YAML,
                breaks_in_ha_version="2026.1.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key=ISSUE_DEPRECATED_YAML,
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            raise
        else:
            async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_DEPRECATED_YAML,
                breaks_in_ha_version="2026.1.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key=ISSUE_DEPRECATED_YAML,
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return config_flow_result

    async def _async_test_config(self, user_input: dict[str, Any]) -> None:
        """Test if the provided configuration is valid."""
        await async_build_and_test_cam_client(self.hass, user_input)
