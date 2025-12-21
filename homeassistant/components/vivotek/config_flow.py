"""Config flow for Vivotek IP cameras integration."""

import logging
from typing import Any

from libpyvivotek.vivotek import SECURITY_LEVELS, VivotekCameraError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
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
    UnitOfFrequency,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import VivotekConfigEntry, build_cam_client
from .camera import DEFAULT_FRAMERATE, DEFAULT_NAME, DEFAULT_STREAM_SOURCE
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
        vol.Required(CONF_FRAMERATE, default=DEFAULT_FRAMERATE): NumberSelector(
            NumberSelectorConfig(min=0, unit_of_measurement=UnitOfFrequency.HERTZ)
        ),
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
            self._async_abort_entries_match(
                {CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
            )
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
                    options={CONF_FRAMERATE: DEFAULT_FRAMERATE},
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
        port = 443 if import_data[CONF_SSL] else 80
        try:
            cam_client = build_cam_client({**import_data, CONF_PORT: port})
            mac_address = await self.hass.async_add_executor_job(cam_client.get_mac)
        except VivotekCameraError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error during camera connection test")
            return self.async_abort(reason="unknown")
        await self.async_set_unique_id(format_mac(mac_address))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, DEFAULT_NAME),
            data={
                CONF_IP_ADDRESS: import_data[CONF_IP_ADDRESS],
                CONF_PORT: port,
                CONF_PASSWORD: import_data[CONF_PASSWORD],
                CONF_USERNAME: import_data[CONF_USERNAME],
                CONF_AUTHENTICATION: import_data[CONF_AUTHENTICATION],
                CONF_SSL: import_data[CONF_SSL],
                CONF_VERIFY_SSL: import_data[CONF_VERIFY_SSL],
                CONF_SECURITY_LEVEL: import_data[CONF_SECURITY_LEVEL],
                CONF_STREAM_PATH: import_data[CONF_STREAM_PATH],
            },
            options={
                CONF_FRAMERATE: import_data[CONF_FRAMERATE],
            },
        )
