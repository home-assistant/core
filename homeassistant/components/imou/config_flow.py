"""Config flow for Imou."""

from collections.abc import Mapping
import logging
from typing import Any, override

from pyimouapi.exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
from pyimouapi.openapi import ImouOpenApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import API_URLS, CONF_API_URL, CONF_APP_ID, CONF_APP_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_APP_SECRET): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class ImouConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Imou integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate credentials and close the temporary client."""
        errors: dict[str, str] = {}
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
        finally:
            await api_client.async_close()
        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_APP_ID])
            self._abort_if_unique_id_configured()
            if not (errors := await self._validate_input(user_input)):
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new App secret."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            if not (
                errors := await self._validate_input(
                    {
                        CONF_APP_ID: reauth_entry.data[CONF_APP_ID],
                        CONF_APP_SECRET: user_input[CONF_APP_SECRET],
                        CONF_API_URL: reauth_entry.data[CONF_API_URL],
                    }
                )
            ):
                await self.async_set_unique_id(reauth_entry.data[CONF_APP_ID])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_APP_SECRET: user_input[CONF_APP_SECRET]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"app_id": reauth_entry.data[CONF_APP_ID]},
            errors=errors,
        )
