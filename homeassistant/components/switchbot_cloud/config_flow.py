"""Config flow for SwitchBot via API integration."""

from logging import getLogger
from typing import Any

from switchbot_api import (
    SwitchBotAPI,
    SwitchBotAuthenticationError,
    SwitchBotConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    DeviceFilterSelectorConfig,
    DeviceSelectorConfig,
)

from .const import DOMAIN, ENTRY_TITLE

_LOGGER = getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class SwitchbotCloudOptionsFlowHandler(OptionsFlow):
    """Handle Switchbot options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Switchbot Cloud options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options: dict[vol.Optional, Any] = {
            vol.Optional(
                "Choice Your Lock Set As Night Light Mode",
            ): selector.DeviceSelector(
                DeviceSelectorConfig(
                    multiple=True,
                    filter=[
                        DeviceFilterSelectorConfig(model="Smart Lock"),
                        DeviceFilterSelectorConfig(model="Smart Lock Lite"),
                        DeviceFilterSelectorConfig(model="Smart Lock Pro"),
                        DeviceFilterSelectorConfig(model="Smart Lock Ultra"),
                    ],
                )
            )
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class SwitchBotCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot via API."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SwitchbotCloudOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SwitchbotCloudOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await SwitchBotAPI(
                    token=user_input[CONF_API_TOKEN], secret=user_input[CONF_API_KEY]
                ).list_devices()
            except SwitchBotConnectionError:
                errors["base"] = "cannot_connect"
            except SwitchBotAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_API_TOKEN], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
