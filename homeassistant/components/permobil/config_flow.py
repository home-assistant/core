"""Config flow for MyPermobil integration."""
from __future__ import annotations

import logging
from typing import Any

from mypermobil import MyPermobil, MyPermobilAPIException, MyPermobilClientException
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_REGION, CONF_TOKEN, CONF_TTL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import APPLICATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

GET_EMAIL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
    }
)

GET_TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_CODE): cv.string})


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_input(p_api: MyPermobil, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    if email := data.get(CONF_EMAIL):
        p_api.set_email(email)
    if code := data.get(CONF_CODE):
        p_api.set_code(code)
    if token := data.get(CONF_TOKEN):
        p_api.set_token(token)


class PermobilConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Permobil config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    p_api: MyPermobil = None
    region_names: dict[str, str] = {"Failed to load regions": ""}
    data: dict[str, str] = {
        CONF_EMAIL: "",
        CONF_REGION: "",
        CONF_CODE: "",
        CONF_TOKEN: "",
        CONF_TTL: "",
    }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        errors: dict[str, str] = {}
        if not self.p_api:
            # create the api instance to use for validation of the user input
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)

        if user_input is not None:
            # the user has entered their email in the first prompt
            user_input[CONF_EMAIL] = user_input[CONF_EMAIL]
            try:
                await validate_input(self.p_api, user_input)
            except MyPermobilClientException as err:
                # the email did not pass validation by the api client
                _LOGGER.error("Permobil: %s", err)
                errors["base"] = "invalid_email"
            self.data[CONF_EMAIL] = user_input[CONF_EMAIL]
            _LOGGER.debug("Permobil: email %s", self.p_api.email)

            await self.async_set_unique_id(self.data[CONF_EMAIL])
            self._abort_if_unique_id_configured()

        if errors or user_input is None:
            # There was an error when the user entered their email
            # or the user opened the flow for the first time
            return self.async_show_form(
                step_id="user", data_schema=GET_EMAIL_SCHEMA, errors=errors
            )
        # email prompt finished successfully, open the select region prompt
        return await self.async_step_region()

    async def async_step_region(self, user_input=None) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        errors: dict[str, str] = {}
        if not self.p_api:
            # create the api for getting regions and sending the code
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)

        if user_input is None:
            # The user has opened the 2nd prompt for the first time
            # fetch the list of regions names and urls from the api
            # for the user to select from. [("name","url"),("name","url"),...]
            try:
                self.region_names = (
                    await self.p_api.request_region_names()
                )  # MyPermobilAPIException
                _LOGGER.debug(
                    "Permobil: region names %s",
                    ",".join(list(self.region_names.keys())),
                )
            except MyPermobilAPIException as err:
                # The backend has returned an error when fetching available regions
                _LOGGER.error("Permobil: %s", err)
                errors["base"] = "region_fetch_error"

        else:
            # the user has selected their region name in the second prompt
            # find the url for the selected region name
            region_url = self.region_names[user_input[CONF_REGION]]
            # set the region url in the api instance and in the entry
            self.data[CONF_REGION] = region_url
            self.p_api.set_region(region_url)
            _LOGGER.debug("Permobil: region %s", self.p_api.region)
            # tell backend to send code to the users email
            # the code will be entered in the next prompt
            try:
                await self.p_api.request_application_code()  # MyPermobilAPIException
            except MyPermobilAPIException as err:
                # the backend has returned an error when requesting the code
                _LOGGER.error("Permobil: %s", err)
                errors["base"] = "region_connection_error"

        if errors or user_input is None:
            # There was an error when the user selected their region
            # or the backend returned an error when trying to send the code
            # or the user opened the second prompt for the first time

            # create the schema for the second prompt, a list of region names
            schema = vol.Schema(
                {
                    vol.Required(CONF_REGION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(self.region_names.keys()),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
            return self.async_show_form(
                step_id="region", data_schema=schema, errors=errors
            )

        # open the email code prompt
        return await self.async_step_email_code()

    async def async_step_email_code(self, user_input=None) -> FlowResult:
        """Second step in config flow to enter the email code."""
        errors: dict[str, str] = {}
        if not self.p_api:
            # create the api to validate the code and to get token
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)

        try:
            if user_input is not None:
                if not user_input.get(CONF_CODE):
                    raise InvalidAuth("empty code")

                # the user has entered data in the second prompt
                # set the data
                user_input[CONF_CODE] = user_input[CONF_CODE].replace(" ", "")
                await validate_input(self.p_api, user_input)  # ClientException
                self.data[CONF_CODE] = user_input[CONF_CODE]
                resp = await self.p_api.request_application_token()  # APIException
                token, ttl = resp  # get token and ttl from the response
                self.data[CONF_TOKEN] = token
                self.data[CONF_TTL] = ttl
                _LOGGER.debug("Permobil: Success")
        except (MyPermobilAPIException, MyPermobilClientException) as err:
            # the code did not pass validation by the api client
            # or the backend returned an error when trying to validate the code
            _LOGGER.error("Permobil: %s", err)
            errors["base"] = "invalid_code"
        except InvalidAuth as err:
            _LOGGER.error("Permobil: %s", err)
            errors["base"] = "empty_code"

        if errors or user_input is None:
            # There was an error when the user entered their code
            # or the user opened the third prompt for the first time
            return self.async_show_form(
                step_id="email_code", data_schema=GET_TOKEN_SCHEMA, errors=errors
            )

        # the entire flow finished successfully
        return self.async_create_entry(title=self.data[CONF_EMAIL], data=self.data)
