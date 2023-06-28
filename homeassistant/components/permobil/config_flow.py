"""Config flow for MyPermobil integration."""
from __future__ import annotations

import logging
from typing import Any

from mypermobil import MyPermobil, MyPermobilAPIException, MyPermobilClientException
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_CODE,
    CONF_EMAIL,
    CONF_REGION,
    CONF_TOKEN,
    CONF_TTL,
    CONF_URL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import APPLICATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

GET_EMAIL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
    }
)

GET_TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_CODE): cv.string})


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_input(p_api: MyPermobil, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    email = data.get(CONF_EMAIL)
    code = data.get(CONF_CODE)
    token = data.get(CONF_TOKEN)
    if email:
        p_api.set_email(email)
    if code:
        code = code.replace(" ", "")
        p_api.set_code(code)
    if token:
        p_api.set_token(token)


class PermobilConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Permobil config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    p_api: MyPermobil = None
    region_names = {"Failed to load regions": ""}
    data = {
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
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if not self.p_api:
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)
        try:
            if user_input is not None:
                # the user has entered data in the first prompt
                await validate_input(self.p_api, user_input)
                self.data[CONF_EMAIL] = user_input[CONF_EMAIL]
                _LOGGER.debug("Permobil: email %s", self.p_api.email)
        except MyPermobilClientException as err:
            _LOGGER.error("Permobil: %s", err)
            errors["base"] = f"Pemobil: {err}"
            errors["reason"] = "invalid_email"
        if errors or user_input is None:
            # there were errors in the first prompt
            return self.async_show_form(
                step_id="user", data_schema=GET_EMAIL_SCHEMA, errors=errors
            )
        # open the email code prompt
        return await self.async_step_region()

    async def async_step_region(self, user_input=None) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        errors: dict[str, str] = {}
        if not self.p_api:
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)
        try:
            if user_input is None:
                include_internal = self.p_api.email.endswith("@permobil.com")
                _LOGGER.debug("Permobil: include internals %s", include_internal)
                self.region_names = await self.p_api.request_region_names(
                    include_internal
                )
                _LOGGER.debug(
                    "Permobil: region names %s", str(self.region_names.keys())
                )

            else:
                # the user has entered data in the first prompt
                # set the data
                await validate_input(self.p_api, user_input)
                region_name = user_input[CONF_REGION]
                self.data[CONF_REGION] = self.region_names[region_name]
                self.p_api.set_region(self.data[CONF_REGION])
                _LOGGER.debug("Permobil: region %s", self.p_api.region)
                await self.p_api.request_application_code()
        except KeyError as err:
            errors["base"] = f"Pemobil: {err}"
            errors["reason"] = "invalid_region"
        except MyPermobilClientException as err:
            errors["base"] = f"Pemobil: {err}"
            errors["reason"] = "invalid_region"
        except MyPermobilAPIException as err:
            errors["base"] = f"Pemobil: {err}"
            errors["reason"] = "connection_error"

        if errors or user_input is None:
            # there were errors in the first prompt
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

        user_input[CONF_URL] = self.region_names[user_input[CONF_REGION]]
        _LOGGER.debug("Permobil: url %s", user_input[CONF_URL])
        # open the email code prompt
        return await self.async_step_email_code()

    async def async_step_email_code(self, user_input=None) -> FlowResult:
        """Second step in config flow to enter the email code."""
        errors: dict[str, str] = {}
        if not self.p_api:
            session = async_get_clientsession(self.hass)
            self.p_api = MyPermobil(APPLICATION, session=session)

        try:
            if user_input is not None:
                # the user has entered data in the second prompt
                # set the data
                await validate_input(self.p_api, user_input)
                self.data[CONF_CODE] = user_input[CONF_CODE]
                _LOGGER.debug("Permobil: code %s…", self.data[CONF_CODE][:3])
                token, ttl = await self.p_api.request_application_token()
                self.data[CONF_TOKEN] = token
                _LOGGER.debug("Permobil: token %s…", self.data[CONF_TOKEN][:5])
                self.data[CONF_TTL] = ttl
                _LOGGER.debug("Permobil: ttl %s", self.data[CONF_TTL])
        except (MyPermobilAPIException, MyPermobilClientException) as err:
            _LOGGER.error("Permobil: %s", err)
            errors["base"] = f"Pemobil: {err}"
            errors["reason"] = "invalid_code"

        if errors or user_input is None:
            return self.async_show_form(
                step_id="email_code", data_schema=GET_TOKEN_SCHEMA, errors=errors
            )

        return self.async_create_entry(title="Token", data=self.data)
