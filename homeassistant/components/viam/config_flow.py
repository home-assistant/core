"""Config flow for viam integration."""

from __future__ import annotations

import logging
from typing import Any

from viam.app.viam_client import ViamClient
from viam.rpc.dial import DialOptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_API_ID,
    CONF_LOCATION,
    CONF_LOCATION_ID,
    CONF_MACHINE,
    CONF_MACHINE_ID,
    CONF_ORG,
    CONF_ORG_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_AUTH_API_KEY_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_client_connection(data: dict[str, Any]) -> ViamClient:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_AUTH_API_KEY_DATA_SCHEMA with values provided by the user.
    """
    api_key_id = data.get(CONF_API_ID)
    api_key = data.get(CONF_API_KEY)

    if not api_key or not api_key_id:
        raise CannotConnect

    opts = DialOptions.with_api_key(api_key, api_key_id)
    client = await ViamClient.create_from_dial_options(opts)

    # If you cannot connect:
    # throw CannotConnect
    if client:
        # Return info that you want to store in the config entry.
        return client

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
        """Handle the initial step - API Key authentication."""
        errors = await self.__handle_auth_input(user_input)
        if errors is None:
            return await self.async_step_organizations()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_AUTH_API_KEY_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_organizations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the organization of the target machine."""
        if user_input is not None:
            self._data.update({CONF_ORG_ID: user_input[CONF_ORG]})
            return await self.async_step_locations()

        app_client = self._client.app_client
        orgs = await app_client.list_organizations()

        if len(orgs) == 1:
            self.__update_with_next_resource(orgs, CONF_ORG_ID)
            return await self.async_step_locations()

        return self.async_show_form(
            step_id="organizations",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORG): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=org.id, label=org.name)
                                for org in orgs
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the location of the target machine."""
        if user_input is not None:
            self._data.update({CONF_LOCATION_ID: user_input[CONF_LOCATION]})
            self._title = (
                await self._client.app_client.get_location(user_input[CONF_LOCATION])
            ).name
            return await self.async_step_machine()

        app_client = self._client.app_client
        locations = await app_client.list_locations(
            org_id=self._data.get(CONF_ORG_ID, "")
        )

        if len(locations) == 1:
            self.__update_with_next_resource(locations, CONF_LOCATION_ID)
            return await self.async_step_machine()

        return self.async_show_form(
            step_id="locations",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=location.id, label=location.name)
                                for location in locations
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_machine(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select target machine from location."""
        if user_input is not None:
            self._data.update({CONF_MACHINE_ID: user_input[CONF_MACHINE]})
            machine = await self._client.app_client.get_robot(user_input[CONF_MACHINE])
            self._title = f"{self._title} - {machine.name}"
            return self.async_create_entry(title=self._title, data=self._data)

        app_client = self._client.app_client
        machines = await app_client.list_robots(self._data.get(CONF_LOCATION_ID, ""))

        if len(machines) == 1:
            self.__update_with_next_resource(machines, CONF_MACHINE_ID)
            return self.async_create_entry(title=self._title, data=self._data)

        return self.async_show_form(
            step_id="machine",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MACHINE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=machine.id, label=machine.name)
                                for machine in machines
                            ]
                        )
                    )
                }
            ),
        )

    @callback
    def async_remove(self) -> None:
        """Notification that the flow has been removed."""
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            _LOGGER.exception("Unexpected exception")

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
                client = await validate_client_connection(self._data)
                self._client = client
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
        else:
            errors = {}

        return errors

    def __update_with_next_resource(self, resource_list: list[Any], resource_key: str):
        resource = next(iter(resource_list))

        if resource_key is CONF_LOCATION_ID:
            self._title = resource.name

        if resource_key is CONF_MACHINE_ID:
            self._title = f"{self._title} - {resource.name}"

        self._data.update({resource_key: resource.id})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
