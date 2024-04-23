"""Config flow for laundrify integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from laundrify_aio import LaundrifyAPI
from laundrify_aio.exceptions import (
    ApiConnectionException,
    InvalidFormat,
    UnknownAuthCode,
)
from voluptuous import Required, Schema

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = Schema({Required(CONF_CODE): str})


class LaundrifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for laundrify."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=CONFIG_SCHEMA)

        errors = {}

        try:
            access_token = await LaundrifyAPI.exchange_auth_code(user_input[CONF_CODE])

            session = async_get_clientsession(self.hass)
            api_client = LaundrifyAPI(access_token, session)

            account_id = await api_client.get_account_id()
        except InvalidFormat:
            errors[CONF_CODE] = "invalid_format"
        except UnknownAuthCode:
            errors[CONF_CODE] = "invalid_auth"
        except ApiConnectionException:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            entry_data = {CONF_ACCESS_TOKEN: access_token}

            await self.async_set_unique_id(account_id)
            self._abort_if_unique_id_configured()

            # Create a new entry if it doesn't exist
            return self.async_create_entry(
                title=DOMAIN,
                data=entry_data,
            )

        return self.async_show_form(
            step_id="init", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=Schema({}),
            )
        return await self.async_step_init()
