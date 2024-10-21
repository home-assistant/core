"""Config flow for viam integration."""

from __future__ import annotations

import logging
from typing import Any

from viam.app.viam_client import ViamClient
from viam.rpc.dial import Credentials, DialOptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_API_ID,
    CONF_CREDENTIAL_TYPE,
    CONF_ROBOT,
    CONF_ROBOT_ID,
    CONF_SECRET,
    CRED_TYPE_API_KEY,
    CRED_TYPE_LOCATION_SECRET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


STEP_AUTH_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CREDENTIAL_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=[
                    CRED_TYPE_API_KEY,
                    CRED_TYPE_LOCATION_SECRET,
                ],
                translation_key=CONF_CREDENTIAL_TYPE,
            )
        )
    }
)
STEP_AUTH_ROBOT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_SECRET): str,
    }
)
STEP_AUTH_ORG_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(data: dict[str, Any]) -> tuple[str, ViamClient]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    credential_type = data[CONF_CREDENTIAL_TYPE]
    auth_entity = data.get(CONF_API_ID)
    secret = data.get(CONF_API_KEY)
    if credential_type == CRED_TYPE_LOCATION_SECRET:
        auth_entity = data.get(CONF_ADDRESS)
        secret = data.get(CONF_SECRET)

    if not secret:
        raise CannotConnect

    creds = Credentials(type=credential_type, payload=secret)
    opts = DialOptions(auth_entity=auth_entity, credentials=creds)
    client = await ViamClient.create_from_dial_options(opts)

    # If you cannot connect:
    # throw CannotConnect
    if client:
        locations = await client.app_client.list_locations()
        location = await client.app_client.get_location(next(iter(locations)).id)

        # Return info that you want to store in the config entry.
        return (location.name, client)

    raise CannotConnect


class ViamFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for viam."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._title = ""
        self._client: ViamClient
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data.update(user_input)

            if self._data.get(CONF_CREDENTIAL_TYPE) == CRED_TYPE_API_KEY:
                return await self.async_step_auth_api_key()

            return await self.async_step_auth_robot_location()

        return self.async_show_form(
            step_id="user", data_schema=STEP_AUTH_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the API Key authentication."""
        errors = await self.__handle_auth_input(user_input)
        if errors is None:
            return await self.async_step_robot()

        return self.async_show_form(
            step_id="auth_api_key",
            data_schema=STEP_AUTH_ORG_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_auth_robot_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the robot location authentication."""
        errors = await self.__handle_auth_input(user_input)
        if errors is None:
            return await self.async_step_robot()

        return self.async_show_form(
            step_id="auth_robot_location",
            data_schema=STEP_AUTH_ROBOT_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_robot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select robot from location."""
        if user_input is not None:
            self._data.update({CONF_ROBOT_ID: user_input[CONF_ROBOT]})
            return self.async_create_entry(title=self._title, data=self._data)

        app_client = self._client.app_client
        locations = await app_client.list_locations()
        robots = await app_client.list_robots(next(iter(locations)).id)

        return self.async_show_form(
            step_id="robot",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROBOT): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=robot.id, label=robot.name)
                                for robot in robots
                            ]
                        )
                    )
                }
            ),
        )

    @callback
    def async_remove(self) -> None:
        """Notification that the flow has been removed."""
        if self._client is not None:
            self._client.close()

    async def __handle_auth_input(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, str] | None:
        """Validate user input for the common authentication logic.

        Returns:
            A dictionary with any handled errors if any occurred, or None

        """
        errors: dict[str, str] | None = None
        if user_input is not None:
            try:
                self._data.update(user_input)
                (title, client) = await validate_input(self._data)
                self._title = title
                self._client = client
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
        else:
            errors = {}

        return errors


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
