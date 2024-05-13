"""Config flow for Hello World integration."""

from __future__ import annotations

import logging
from typing import Any

from aidot.login_control import LoginControl
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import (
    CLOUD_SERVERS,
    CONF_CHOOSE_HOUSE,
    CONF_PASSWORD,
    CONF_SERVER_COUNTRY,
    CONF_USERNAME,
    DOMAIN,
)

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

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # get ContryCode
                selected_contry_name = user_input[CONF_SERVER_COUNTRY]
                selected_contry_obj = {}
                for item in CLOUD_SERVERS:
                    if item["name"] == selected_contry_name:
                        selected_contry_obj = item
                        break
                self.__login_control.change_country_code(selected_contry_obj)

                self.login_response = await self.__login_control.async_post_login(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                self.accessToken = self.login_response["accessToken"]

                # get houses
                self.house_list = await self.__login_control.async_get_houses(
                    self.hass, self.accessToken
                )

                return await self.async_step_choose_house()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "login_failed"

        if user_input is None:
            user_input = {}

        counties_name = [item["name"] for item in CLOUD_SERVERS]
        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_SERVER_COUNTRY,
                    default=user_input.get(CONF_SERVER_COUNTRY, "United States"),
                ): vol.In(counties_name),
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

    async def async_step_choose_house(self, user_input=None):
        """Please select a room."""
        errors = {}
        if user_input is None:
            user_input = {}

        if user_input.get(CONF_CHOOSE_HOUSE) is not None:
            # get all house name
            for item in self.house_list:
                if item["name"] == user_input.get(CONF_CHOOSE_HOUSE):
                    self.selected_house = item

            # get device_list
            self.device_list = await self.__login_control.async_get_devices(
                self.hass, self.accessToken, self.selected_house["id"]
            )

            # get product_list
            productIds = ",".join([item["productId"] for item in self.device_list])
            self.product_list = await self.__login_control.async_get_products(
                self.hass, self.accessToken, productIds
            )

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
