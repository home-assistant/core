"""Config flow for the Gatus integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from gatus_api import GatusAuthError, GatusClient, GatusClientError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
        vol.Optional(CONF_TOKEN): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            ),
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate that the user input allows us to connect to Gatus and return data."""
    client = GatusClient(
        url=data[CONF_URL],
        session=async_get_clientsession(hass),
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        token=data.get(CONF_TOKEN),
    )

    try:
        await client.get_endpoints_statuses()
    except GatusAuthError as err:
        _LOGGER.debug(
            "Authentication failed for Gatus instance at %s: %s", data[CONF_URL], err
        )
        raise InvalidAuth from err
    except GatusClientError as err:
        _LOGGER.debug("Cannot connect to Gatus instance at %s: %s", data[CONF_URL], err)
        raise CannotConnect from err


class GatusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gatus."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step when adding the integration via the UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if URL(user_input[CONF_URL]).host is not None:
                user_input[CONF_URL] = str(
                    URL(user_input[CONF_URL])
                    .with_query(None)
                    .with_fragment(None)
                    .with_user(None)
                    .with_password(None)
                ).rstrip("/")

            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Gatus setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Gatus", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            if URL(user_input[CONF_URL]).host is not None:
                user_input[CONF_URL] = str(
                    URL(user_input[CONF_URL])
                    .with_query(None)
                    .with_fragment(None)
                    .with_user(None)
                    .with_password(None)
                ).rstrip("/")

            if user_input[CONF_URL] != reconfigure_entry.data[CONF_URL]:
                self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Gatus reconfigure")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        suggested_values = {
            key: val
            for key, val in (user_input or reconfigure_entry.data).items()
            if key not in (CONF_PASSWORD, CONF_TOKEN)
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request from Home Assistant."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            user_input[CONF_URL] = reauth_entry.data[CONF_URL]
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Gatus reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT,
                        autocomplete="username",
                    ),
                ),
                vol.Optional(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    ),
                ),
                vol.Optional(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                    ),
                ),
            }
        )

        suggested_values = {
            key: val
            for key, val in (user_input or reauth_entry.data).items()
            if key not in (CONF_PASSWORD, CONF_TOKEN)
        }

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(schema, suggested_values),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the server."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
