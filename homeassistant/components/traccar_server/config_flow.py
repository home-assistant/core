"""Config flow for Traccar Server integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytraccar import (
    ApiClient,
    ServerModel,
    TraccarAuthenticationException,
    TraccarException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_EVENTS,
    CONF_MAX_ACCURACY,
    CONF_SKIP_ACCURACY_FILTER_FOR,
    DOMAIN,
    EVENTS,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_PORT, default="8082"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_SSL, default=False): BooleanSelector(BooleanSelectorConfig()),
        vol.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(
            BooleanSelectorConfig()
        ),
    }
)

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        schema=vol.Schema(
            {
                vol.Optional(CONF_MAX_ACCURACY, default=0.0): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.BOX,
                        min=0.0,
                    )
                ),
                vol.Optional(CONF_CUSTOM_ATTRIBUTES, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        sort=True,
                        custom_value=True,
                        options=[],
                    )
                ),
                vol.Optional(CONF_SKIP_ACCURACY_FILTER_FOR, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        sort=True,
                        custom_value=True,
                        options=[],
                    )
                ),
                vol.Optional(CONF_EVENTS, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        sort=True,
                        custom_value=True,
                        options=list(EVENTS),
                    )
                ),
            }
        )
    ),
}


class TraccarServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Traccar Server."""

    async def _get_server_info(self, user_input: dict[str, Any]) -> ServerModel:
        """Get server info."""
        client = ApiClient(
            client_session=async_get_clientsession(self.hass),
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            ssl=user_input[CONF_SSL],
            verify_ssl=user_input[CONF_VERIFY_SSL],
        )
        return await client.get_server()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )
            try:
                await self._get_server_info(user_input)
            except TraccarException as exception:
                LOGGER.error("Unable to connect to Traccar Server: %s", exception)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            test_data = {
                **reauth_entry.data,
                **user_input,
            }
            try:
                await self._get_server_info(test_data)
            except TraccarAuthenticationException:
                LOGGER.error("Invalid credentials for Traccar Server")
                errors["base"] = "invalid_auth"
            except TraccarException as exception:
                LOGGER.error("Unable to connect to Traccar Server: %s", exception)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )
        username = (
            user_input[CONF_USERNAME]
            if user_input
            else reauth_entry.data[CONF_USERNAME]
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=username): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.EMAIL)
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                CONF_HOST: reauth_entry.data[CONF_HOST],
                CONF_PORT: reauth_entry.data[CONF_PORT],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
