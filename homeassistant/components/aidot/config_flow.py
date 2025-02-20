"""Config flow for Aidot integration."""

from __future__ import annotations

import logging
from typing import Any

from aidot.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_LIST,
    CONF_ID,
    CONF_IS_DEFAULT,
    CONF_LOGIN_RESPONSE,
    CONF_NAME,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_LIST,
    CONF_SELECTED_HOUSE,
    DEFAULT_COUNTRY_NAME,
    SUPPORTED_COUNTRY_NAMES,
)
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

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()
        self.login_response: dict[str, Any] = {}
        self.accessToken: str = ""
        self.house_list: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        selected_contry_name = DEFAULT_COUNTRY_NAME
        input_username: str = ""
        input_password: str = ""
        if user_input is not None:
            # get ContryCode
            selected_contry_name = user_input[CONF_COUNTRY]
            self.__login_control.change_country_name(selected_contry_name)
            input_username = user_input[CONF_USERNAME]
            input_password = user_input[CONF_PASSWORD]
            try:
                self.login_response = await self.__login_control.async_post_login(
                    self.hass,
                    input_username,
                    input_password,
                )
                if self.login_response is None:
                    errors["base"] = "login_failed"
                if not errors:
                    self.accessToken = self.login_response[CONF_ACCESS_TOKEN]
                    # get houses
                    self.house_list = await self.__login_control.async_get_houses(
                        self.hass, self.accessToken
                    )
                    if self.house_list is None or len(self.house_list) == 0:
                        errors["base"] = "get_house_failed"
                if not errors:
                    return await self.async_step_choose_house()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_COUNTRY,
                    default=selected_contry_name,
                ): vol.In(SUPPORTED_COUNTRY_NAMES),
                vol.Required(CONF_USERNAME, default=input_username): str,
                vol.Required(CONF_PASSWORD, default=input_password): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_choose_house(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Please select a room."""
        errors: dict[str, str] = {}
        selected_house: dict[str, Any] = {}

        if user_input is not None:
            selected_house = next(
                (
                    item
                    for item in self.house_list
                    if item[CONF_NAME] == user_input[CONF_CHOOSE_HOUSE]
                ),
                {},
            )
            identifier = self.__login_control.get_identifier(selected_house[CONF_ID])
            await self.async_set_unique_id(identifier)
            self._abort_if_unique_id_configured()
            try:
                # get device_list
                device_list: list[
                    dict[str, Any]
                ] = await self.__login_control.async_get_devices(
                    self.hass, self.accessToken, selected_house[CONF_ID]
                )
                product_list: list[dict[str, Any]] = []
                if device_list is not None:
                    # get product_list
                    productIds = ",".join(
                        [item[CONF_PRODUCT_ID] for item in device_list]
                    )
                    product_list = await self.__login_control.async_get_products(
                        self.hass, self.accessToken, productIds
                    )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"

            title = self.__login_control.username + " " + selected_house[CONF_NAME]
            return self.async_create_entry(
                title=title,
                data={
                    CONF_LOGIN_RESPONSE: self.login_response,
                    CONF_SELECTED_HOUSE: selected_house,
                    CONF_DEVICE_LIST: device_list,
                    CONF_PRODUCT_LIST: product_list,
                },
            )

        if len(selected_house) == 0:
            selected_house = next(
                (item for item in self.house_list if item[CONF_IS_DEFAULT] is not None),
                {},
            )
        house_name_list = [item[CONF_NAME] for item in self.house_list]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHOOSE_HOUSE,
                    default=selected_house[CONF_NAME],
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
