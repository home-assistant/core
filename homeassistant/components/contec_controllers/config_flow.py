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
        vol.Required("number_of_controllers"): int,
        vol.Required("port"): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    number_of_controllers: int = data["number_of_controllers"]
    controllers_ip: str = data["ip"]
    controllers_port: int = data["port"]
    controller_manager: ControllerManager = ControllerManager(
        ContecTracer(logging.getLogger("ContecControllers")),
        ContecConectivityConfiguration(
            number_of_controllers,
            controllers_ip,
            controllers_port,
        ),
    )

    try:
        controller_manager.Init()
        if not await controller_manager.IsConnected(timedelta(seconds=7)):
            _LOGGER.warning(
                f"Failed to connect to Contec Controllers at address {controllers_ip},{controllers_port}"
            )
            raise CannotConnect
    finally:
        await controller_manager.CloseAsync()

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
