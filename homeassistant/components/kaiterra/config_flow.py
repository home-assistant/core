"""Config flow for the Kaiterra integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api_data import (
    KaiterraApiAuthError,
    KaiterraApiClient,
    KaiterraApiError,
    KaiterraDeviceNotFoundError,
)
from .const import (
    AVAILABLE_AQI_STANDARDS,
    CONF_AQI_STANDARD,
    DEFAULT_AQI_STANDARD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
        vol.Required(CONF_DEVICE_ID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    await KaiterraApiClient(
        async_get_clientsession(hass),
        data[CONF_API_KEY],
        DEFAULT_AQI_STANDARD,
    ).async_get_latest_sensor_readings(data[CONF_DEVICE_ID])


class KaiterraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kaiterra."""

    VERSION = 1
    MINOR_VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()

            try:
                await validate_input(self.hass, user_input)
            except KaiterraApiAuthError:
                errors["base"] = "invalid_auth"
            except KaiterraDeviceNotFoundError:
                errors["base"] = "device_not_found"
            except KaiterraApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE_ID], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA,
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle the start of a reauthentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API key."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    {
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_DEVICE_ID: reauth_entry.data[CONF_DEVICE_ID],
                    },
                )
            except KaiterraApiAuthError:
                errors["base"] = "invalid_auth"
            except KaiterraApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KaiterraOptionsFlowHandler:
        """Return the options flow."""
        return KaiterraOptionsFlowHandler()


class KaiterraOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Kaiterra options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Kaiterra options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_AQI_STANDARD, default=DEFAULT_AQI_STANDARD): vol.In(
                    AVAILABLE_AQI_STANDARDS
                )
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                self.config_entry.options or {CONF_AQI_STANDARD: DEFAULT_AQI_STANDARD},
            ),
        )
