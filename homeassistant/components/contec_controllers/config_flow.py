"""Config flow for Contec Controllers integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from ContecControllers.ContecConectivityConfiguration import (
    ContecConectivityConfiguration,
)
from ContecControllers.ControllerManager import ControllerManager
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .contec_tracer import ContecTracer

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("ip"): str,
        vol.Required("numberOfControllers"): int,
        vol.Required("port"): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    numberOfControllers: int = data["numberOfControllers"]
    controllersIp: str = data["ip"]
    controllersPort: int = data["port"]
    controllerManager: ControllerManager = ControllerManager(
        ContecTracer(logging.getLogger("ContecControllers")),
        ContecConectivityConfiguration(
            numberOfControllers,
            controllersIp,
            controllersPort,
        ),
    )

    try:
        controllerManager.Init()
        if not await controllerManager.IsConnected(timedelta(seconds=7)):
            _LOGGER.warning(
                f"Failed to connect to Contec Controllers at address {controllersIp},{controllersPort}"
            )
            raise CannotConnect
    finally:
        await controllerManager.CloseAsync()

    return {"title": "ContecControllers"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Contec Controllers."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
