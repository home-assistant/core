"""Config flow for MyPermobil integration."""
from __future__ import annotations

from collections.abc import Mapping
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


class PermobilConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Permobil config flow."""

    VERSION = 1
    p_api: MyPermobil = None
    region_names: dict[str, str] = {}
    data: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        self.p_api = MyPermobil(APPLICATION, session=session)

        if user_input is not None:
            try:
                self.p_api.set_email(user_input[CONF_EMAIL])
            except MyPermobilClientException as err:
                _LOGGER.error("Error validating email: %s", err)
                errors["base"] = "invalid_email"

            self.data.update(user_input)

            await self.async_set_unique_id(self.data[CONF_EMAIL])
            self._abort_if_unique_id_configured()

        if errors or user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=GET_EMAIL_SCHEMA, errors=errors
            )

        return await self.async_step_region()

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        errors: dict[str, str] = {}
        if user_input is None:
            # fetch the list of regions names and urls from the api
            # for the user to select from.
            try:
                self.region_names = await self.p_api.request_region_names()
                _LOGGER.debug(
                    "region names %s",
                    ",".join(list(self.region_names.keys())),
                )
            except MyPermobilAPIException as err:
                _LOGGER.error("Error requesting regions: %s", err)
                errors["base"] = "region_fetch_error"

        else:
            region_url = self.region_names[user_input[CONF_REGION]]

            self.data[CONF_REGION] = region_url
            self.p_api.set_region(region_url)
            _LOGGER.debug("region %s", self.p_api.region)
            try:
                # tell backend to send code to the users email
                await self.p_api.request_application_code()
            except MyPermobilAPIException as err:
                _LOGGER.error("Error requesting code: %s", err)
                errors["base"] = "region_connection_error"

        if errors or user_input is None:
            # the error could either be that the fetch region did not pass
            # or that the request application code failed
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

        return await self.async_step_email_code()

    async def async_step_email_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Second step in config flow to enter the email code."""
        errors: dict[str, str] = {}

        try:
            if user_input is not None:
                self.p_api.set_code(user_input[CONF_CODE])
                self.data.update(user_input)
                token, ttl = await self.p_api.request_application_token()
                self.data[CONF_TOKEN] = token
                self.data[CONF_TTL] = ttl
                _LOGGER.debug("Success")
        except (MyPermobilAPIException, MyPermobilClientException) as err:
            # the code did not pass validation by the api client
            # or the backend returned an error when trying to validate the code
            _LOGGER.error("Error verifying code: %s", err)
            errors["base"] = "invalid_code"

        if errors or user_input is None:
            return self.async_show_form(
                step_id="email_code", data_schema=GET_TOKEN_SCHEMA, errors=errors
            )

        return self.async_create_entry(title=self.data[CONF_EMAIL], data=self.data)

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        errors: dict[str, str] = {}
        if not self.p_api:
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)

        reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id", "")
        )

        if reauth_entry:
            email: str = reauth_entry.data[CONF_EMAIL]
            region: str = reauth_entry.data[CONF_REGION]
            self.p_api.set_email(email)
            self.p_api.set_region(region)
            self.data = {
                CONF_EMAIL: email,
                CONF_REGION: region,
            }

            try:
                await self.p_api.request_application_code()
            except MyPermobilAPIException as err:
                _LOGGER.error("Error requesting code: %s", err)
                errors["base"] = "region_connection_error"
        else:
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(step_id="reauth", errors=errors)
        return await self.async_step_email_code()
