"""Config flow for Imou."""

import logging
from typing import Any

from pyimouapi.exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
from pyimouapi.openapi import ImouOpenApiClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    API_URLS,
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_OPTION_LIVE_RESOLUTION,
    CONF_OPTION_UPDATE_INTERVAL,
    DEFAULT_LIVE_RESOLUTION,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    LIVE_RESOLUTION_HD,
    LIVE_RESOLUTION_SD,
    MAX_UPDATE_INTERVAL_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class ImouConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Imou integration."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ImouOptionsFlow:
        """Return the options flow handler."""
        return ImouOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_APP_ID])
            self._abort_if_unique_id_configured()
            api_client = ImouOpenApiClient(
                user_input[CONF_APP_ID],
                user_input[CONF_APP_SECRET],
                API_URLS[user_input[CONF_API_URL]],
            )
            try:
                await api_client.async_get_token()
            except InvalidAppIdOrSecretException:
                errors["base"] = "invalid_auth"
            except ConnectFailedException, RequestFailedException:
                errors["base"] = "cannot_connect"
            except ImouException as exception:
                _LOGGER.debug("Imou error during config flow: %s", exception)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Imou",
                    data={
                        CONF_APP_ID: user_input[CONF_APP_ID],
                        CONF_APP_SECRET: user_input[CONF_APP_SECRET],
                        CONF_API_URL: user_input[CONF_API_URL],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_ID): str,
                    vol.Required(CONF_APP_SECRET): str,
                    vol.Required(CONF_API_URL, default="sg"): SelectSelector(
                        SelectSelectorConfig(
                            options=list(API_URLS),
                            translation_key="api_url",
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )


class ImouOptionsFlow(OptionsFlow):
    """Handle Imou options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Imou options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_OPTION_LIVE_RESOLUTION,
                            default=DEFAULT_LIVE_RESOLUTION,
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[LIVE_RESOLUTION_HD, LIVE_RESOLUTION_SD],
                                translation_key=CONF_OPTION_LIVE_RESOLUTION,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Required(
                            CONF_OPTION_UPDATE_INTERVAL,
                            default=DEFAULT_UPDATE_INTERVAL_SECONDS,
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_UPDATE_INTERVAL_SECONDS,
                                max=MAX_UPDATE_INTERVAL_SECONDS,
                                mode=NumberSelectorMode.BOX,
                                unit_of_measurement="s",
                            )
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
