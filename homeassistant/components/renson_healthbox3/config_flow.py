"""Config flow for Renson Healthbox integration."""
from __future__ import annotations

from typing import Any

from pyhealthbox3.healthbox3 import (
    Healthbox3,
    Healthbox3ApiClientAuthenticationError,
    Healthbox3ApiClientCommunicationError,
    Healthbox3ApiClientError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, LOGGER


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Renson Healthbox."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                if CONF_API_KEY in user_input:
                    await self._test_credentials(
                        ipaddress=user_input[CONF_HOST],
                        apikey=user_input[CONF_API_KEY],
                    )
                else:
                    await self._test_connectivity(ipaddress=user_input[CONF_HOST])
            except Healthbox3ApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except Healthbox3ApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except Healthbox3ApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_HOST]}")
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                    vol.Optional(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, ipaddress: str, apikey: str) -> None:
        """Validate credentials."""
        client = Healthbox3(
            host=ipaddress,
            api_key=apikey,
            session=async_create_clientsession(self.hass),
        )
        await client.async_enable_advanced_api_features()

    async def _test_connectivity(self, ipaddress: str) -> None:
        """Validate connectivity."""
        client = Healthbox3(
            host=ipaddress,
            api_key=None,
            session=async_create_clientsession(self.hass),
        )
        await client.async_validate_connectivity()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for the Config Entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        errors = {}
        host: str = self.entry.data[CONF_HOST] if CONF_HOST in self.entry.data else ""
        if user_input is not None:
            if (api_key := user_input.get(CONF_API_KEY)) is None:
                errors[CONF_API_KEY] = "Invalid API Key"
            else:
                try:
                    self.hass.config_entries.async_update_entry(
                        entry=self.entry,
                        data={CONF_HOST: host, CONF_API_KEY: user_input[CONF_API_KEY]},
                    )
                    hb3 = Healthbox3(host=host, api_key=api_key)
                    await hb3.async_enable_advanced_api_features(pre_validation=False)
                    await hb3.close()
                except Healthbox3ApiClientAuthenticationError:
                    pass
                finally:
                    errors[CONF_API_KEY] = "Invalid API Key"

                return self.async_create_entry(
                    title="", data=user_input | {CONF_API_KEY: api_key or None}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=self.entry.data.get(CONF_API_KEY, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )
