"""Config flow for viam integration."""
from __future__ import annotations

import logging
from typing import Any

from viam.app.viam_client import ViamClient
from viam.rpc.dial import Credentials, DialOptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_AUTH_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("credential_type"): selector(
            {
                "select": {
                    "options": [
                        {"value": "api-key", "label": "Org API Key"},
                        {
                            "value": "robot-location-secret",
                            "label": "Robot Location Secret",
                        },
                    ],
                    "translation_key": "credential_type",
                }
            }
        )
    }
)
STEP_AUTH_ROBOT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("address"): str,
        vol.Required("secret"): str,
    }
)
STEP_AUTH_ORG_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("api_id"): str,
        vol.Required("api_key"): str,
    }
)


class ViamHub:
    """Collect user input during config flow and wrap ViamClient authentication logic."""

    def __init__(self, auth_entity: str, credential_type: str) -> None:
        """Initialize."""
        self.auth_entity = auth_entity
        self.credential_type = credential_type
        self.client: ViamClient | None = None

    async def authenticate(self, secret: str) -> bool:
        """Test if we can authenticate with the host."""
        creds = Credentials(type=self.credential_type, payload=secret)
        opts = DialOptions(auth_entity=self.auth_entity, credentials=creds)
        self.client = await ViamClient.create_from_dial_options(opts)
        return bool(self.client)

    def close(self) -> None:
        """Close out the open client if it exists."""
        if self.client:
            self.client.close()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    credential_type = data["credential_type"]
    auth_entity = data["api_id"]
    secret = data["api_key"]
    if credential_type == "robot-location-secret":
        auth_entity = data["address"]
        secret = data["secret"]

    hub = ViamHub(
        auth_entity,
        data["credential_type"],
    )

    if not await hub.authenticate(secret):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth
    if hub.client:
        locations = await hub.client.app_client.list_locations()
        location = await hub.client.app_client.get_location(next(iter(locations)).id)

        # Return info that you want to store in the config entry.
        return {"title": location.name, "hub": hub}

    raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for viam."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.credential_type = None
        self.info = {}
        self.data = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.credential_type = user_input["credential_type"]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user", data_schema=STEP_AUTH_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.info = await validate_input(
                    self.hass, {"credential_type": self.credential_type, **user_input}
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.data = user_input
                return await self.async_step_robot()

        schema = STEP_AUTH_ROBOT_DATA_SCHEMA
        if self.credential_type == "api-key":
            schema = STEP_AUTH_ORG_DATA_SCHEMA

        return self.async_show_form(
            step_id="auth",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_robot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select robot from location."""

        locations = await self.info["hub"].client.app_client.list_locations()
        robots = await self.info["hub"].client.app_client.list_robots(
            next(iter(locations)).id
        )
        if user_input is not None:
            robot_id = next(
                robot.id for robot in robots if robot.name == user_input["robot"]
            )
            self.data.update(
                {"robot_id": robot_id, "credential_type": self.credential_type}
            )
            self.info["hub"].close()
            return self.async_create_entry(title=self.info["title"], data=self.data)

        return self.async_show_form(
            step_id="robot",
            data_schema=vol.Schema(
                {
                    vol.Required("robot"): selector(
                        {"select": {"options": [robot.name for robot in robots]}}
                    )
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
