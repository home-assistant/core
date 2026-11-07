"""Config flow for Axle Energy."""

from collections.abc import Mapping
from typing import Any, override

from aioaxlevpp import (
    AxleAuthenticationError,
    AxleClient,
    AxleConnectionError,
    AxleError,
)
import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

STEP_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class AxleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the household's Axle event feed."""

    async def _validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Check a token with the service, including when no event is scheduled."""
        client = AxleClient(
            async_get_clientsession(self.hass), user_input[CONF_API_KEY]
        )
        try:
            await client.get_event()
        except AxleAuthenticationError:
            return {"base": "invalid_auth"}
        except AxleConnectionError:
            return {"base": "cannot_connect"}
        except AxleError:
            return {"base": "cannot_retrieve"}
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the household event feed."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            if not (errors := await self._validate(user_input)):
                return self.async_create_entry(title="Axle Energy", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            description_placeholders={
                "token_url": "https://vpp.axle.energy/app/account/home-assistant"
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle an API key that is no longer accepted."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate a replacement API key and reload the existing feed."""
        return await self._async_update_api_key(
            self._get_reauth_entry(), "reauth_confirm", user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to update the API key before authentication fails."""
        return await self._async_update_api_key(
            self._get_reconfigure_entry(), "reconfigure", user_input
        )

    async def _async_update_api_key(
        self,
        entry: ConfigEntry,
        step_id: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate the API key for an existing feed."""
        errors = {}
        if user_input is not None:
            try:
                self._async_abort_entries_match(
                    {CONF_API_KEY: user_input[CONF_API_KEY]}
                )
            except AbortFlow:
                errors[CONF_API_KEY] = "already_configured"
            else:
                if not (errors := await self._validate(user_input)):
                    return self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_SCHEMA,
                (user_input or entry.data)
                if self.source == SOURCE_RECONFIGURE
                else None,
            ),
            description_placeholders={
                "token_url": "https://vpp.axle.energy/app/account/home-assistant"
            },
            errors=errors,
        )
