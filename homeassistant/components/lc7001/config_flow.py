"""Config flow for the Legrand Whole Home Lighting integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.exceptions import HomeAssistantError, IntegrationError

from .const import DEFAULT_HOST, DEFAULT_PORT, DEVICE_HUB, DOMAIN
from .engine.engine import ConnectionState, Engine

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PASSWORD): str,
    }
)


class LcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Legrand Whole Home Lighting."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.data: dict[str, Any] = {}

    async def validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the user input allows us to connect."""

        host = data[CONF_HOST]
        port = data[CONF_PORT]
        password = data[CONF_PASSWORD]

        if host is None:
            raise ConfigEntryNotReady
        if port is None:
            raise ConfigEntryNotReady
        if password is None:
            raise ConfigEntryNotReady

        try:
            engine = Engine(host=host, port=port, password=password)

            engine.connect()
            engine.start()

            await engine.waitForState(ConnectionState.Ready)
            mac = engine.systemInfo.MACAddress

        except TimeoutError as error:
            raise CannotConnect from error

        finally:
            engine.disconnect()

        # Return info that you want to store in the config entry.
        return {"title": DEVICE_HUB, "mac": mac}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input:
            try:
                info = await self.validate_input(data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ConfigEntryNotReady(IntegrationError):
    """Error to indicate there is invalid config."""
