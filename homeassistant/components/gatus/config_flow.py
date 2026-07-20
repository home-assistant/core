"""Config flow for the Gatus integration."""

import logging
from typing import Any, override

from gatus_api import GatusClient, GatusClientError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate that the user input allows us to connect to Gatus and return data."""
    client = GatusClient(url=data[CONF_URL], session=async_get_clientsession(hass))

    try:
        await client.get_endpoints_statuses()
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
            url = URL(user_input[CONF_URL])
            user_input[CONF_URL] = str(
                url.with_query(None)
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
            except Exception:
                _LOGGER.exception("Unexpected exception during Gatus reconfigure")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the server."""
