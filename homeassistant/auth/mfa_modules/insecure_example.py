"""Example auth module."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.core import HomeAssistant

from . import (
    MULTI_FACTOR_AUTH_MODULE_SCHEMA,
    MULTI_FACTOR_AUTH_MODULES,
    MultiFactorAuthModule,
    SetupFlow,
)

CONFIG_SCHEMA = MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend(
    {
        vol.Required("data"): [
            vol.Schema({vol.Required("user_id"): str, vol.Required("pin"): str})
        ]
    },
    extra=vol.PREVENT_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


@MULTI_FACTOR_AUTH_MODULES.register("insecure_example")
class InsecureExampleModule(MultiFactorAuthModule):
    """Example auth module validate pin."""

    DEFAULT_TITLE = "Insecure Personal Identify Number"

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]) -> None:
        """Initialize the user data store."""
        super().__init__(hass, config)
        self._data = config["data"]

    @property
    def input_schema(self) -> vol.Schema:
        """Validate login flow input data."""
        return vol.Schema({"pin": str})

    @property
    def setup_schema(self) -> vol.Schema:
        """Validate async_setup_user input data."""
        return vol.Schema({"pin": str})

    async def async_setup_flow(self, user_id: str) -> SetupFlow:
        """Return a data entry flow handler for setup module.

        Mfa module should extend SetupFlow
        """
        return SetupFlow(self, self.setup_schema, user_id)

    async def async_setup_user(self, user_id: str, setup_data: Any) -> Any:
        """Set up user to use mfa module."""
        # data shall has been validate in caller
        pin = setup_data["pin"]

        for data in self._data:
            if data["user_id"] == user_id:
                # already setup, override
                data["pin"] = pin
                return

        self._data.append({"user_id": user_id, "pin": pin})

    async def async_depose_user(self, user_id: str) -> None:
        """Remove user from mfa module."""
        found = None
        for data in self._data:
            if data["user_id"] == user_id:
                found = data
                break
        if found:
            self._data.remove(found)

    async def async_is_user_setup(self, user_id: str) -> bool:
        """Return whether user is setup."""
        for data in self._data:
            if data["user_id"] == user_id:
                return True
        return False

    async def async_validate(self, user_id: str, user_input: Dict[str, Any]) -> bool:
        """Return True if validation passed."""
        for data in self._data:
            if data["user_id"] == user_id:
                # user_input has been validate in caller
                if data["pin"] == user_input["pin"]:
                    return True

        return False
