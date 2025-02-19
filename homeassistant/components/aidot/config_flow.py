"""Config flow for Aidot integration."""

from __future__ import annotations

import logging
from typing import Any

from aidot.login_const import DEFAULT_COUNTRY_NAME, SUPPORTED_COUNTRY_NAMES
from aidot.login_control import LoginControl
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_CHOOSE_HOUSE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data["host"]) < 3:
        raise InvalidHost
    return {"title": data["host"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle aidot config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()
        self.login_response: dict[Any, Any] = {}
        self.accessToken = ""
        self.house_list: list[Any] = []
        self.device_list: list[Any] = []
        self.product_list: list[Any] = []
        self.selected_house: dict[Any, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                # get ContryCode
                selected_contry_name = user_input[CONF_COUNTRY]
                self.__login_control.change_country_name(selected_contry_name)

                self.login_response = await self.__login_control.async_post_login(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                if self.login_response is None:
                    errors["base"] = "login_failed"
                    return self.async_show_form(
                        step_id="user", data_schema=None, errors=errors
                    )
                self.accessToken = self.login_response["accessToken"]

                # get houses
                self.house_list = await self.__login_control.async_get_houses(
                    self.hass, self.accessToken
                )
                if self.house_list is None or len(self.house_list) == 0:
                    errors["base"] = "get_house_failed"
                    return self.async_show_form(
                        step_id="user", data_schema=None, errors=errors
                    )

                return await self.async_step_choose_house()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"
        if user_input is None:
            user_input = {}

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_COUNTRY,
                    default=user_input.get(CONF_COUNTRY, DEFAULT_COUNTRY_NAME),
                ): vol.In(SUPPORTED_COUNTRY_NAMES),
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, vol.UNDEFINED)
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, vol.UNDEFINED)
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_choose_house(self, user_input=None) -> ConfigFlowResult:
        """Please select a room."""
        errors: dict[str, str] = {}
        if user_input is None:
            user_input = {}

        if user_input.get(CONF_CHOOSE_HOUSE) is not None:
            try:
                # get all house name
                for item in self.house_list:
                    if item["name"] == user_input.get(CONF_CHOOSE_HOUSE):
                        self.selected_house = item
                identifier = self.__login_control.get_identifier(
                    self.selected_house["id"]
                )
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()

                # get device_list
                self.device_list = await self.__login_control.async_get_devices(
                    self.hass, self.accessToken, self.selected_house["id"]
                )
                if self.device_list is not None:
                    # get product_list
                    productIds = ",".join(
                        [item["productId"] for item in self.device_list]
                    )
                    self.product_list = await self.__login_control.async_get_products(
                        self.hass, self.accessToken, productIds
                    )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"

            title = self.login_response["username"] + " " + self.selected_house["name"]
            return self.async_create_entry(
                title=title,
                data={
                    "login_response": self.login_response,
                    "selected_house": self.selected_house,
                    "device_list": self.device_list,
                    "product_list": self.product_list,
                },
            )

        # get default house
        default_house = {}
        for item in self.house_list:
            if item["isDefault"]:
                default_house = item

        # get all house name
        house_name_list = [item["name"] for item in self.house_list]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHOOSE_HOUSE,
                    default=user_input.get(CONF_CHOOSE_HOUSE, default_house["name"]),
                ): vol.In(house_name_list)
            }
        )
        return self.async_show_form(
            step_id="choose_house",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
