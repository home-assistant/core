"""Config flow for Aidot integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aidot.client import AidotClient
from aidot.const import CONF_LOGIN_INFO, DEFAULT_COUNTRY_NAME, SUPPORTED_COUNTRY_NAMES
from aidot.exceptions import AidotUserOrPassIncorrect, InvalidHost
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

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

    _entry_data: Mapping[str, Any]

    def __init__(self) -> None:
        """Initialize the config flow."""

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the reauth step."""
        self._entry_data = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a Confirm flow for reauthentication with password."""
        client = AidotClient(
            session=async_get_clientsession(self.hass),
            token=self._entry_data[CONF_LOGIN_INFO],
        )
        errors = {}
        entry = await self.async_set_unique_id(client.get_identifier())

        if not entry:
            return self.async_abort(reason="aidot_cloud_account_missing")

        if user_input is not None:
            client.update_password(user_input[CONF_PASSWORD])
            try:
                login_info = await client.async_post_login()
                if login_info is None:
                    errors["base"] = "login_failed"
                if not errors:
                    return self.async_update_reload_and_abort(
                        entry, data={CONF_LOGIN_INFO: login_info}
                    )
            except AidotUserOrPassIncorrect:
                errors["base"] = "account_pwd_incorrect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = AidotClient(
                session=async_get_clientsession(self.hass),
                country_name=user_input[CONF_COUNTRY],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            await self.async_set_unique_id(client.get_identifier())
            self._abort_if_unique_id_configured()
            try:
                login_info = await client.async_post_login()
                if login_info is None:
                    errors["base"] = "login_failed"
                if not errors:
                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME]
                        + " "
                        + user_input[CONF_COUNTRY],
                        data={
                            CONF_LOGIN_INFO: login_info,
                        },
                    )
            except AidotUserOrPassIncorrect:
                errors["base"] = "account_pwd_incorrect"

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_COUNTRY,
                    default=DEFAULT_COUNTRY_NAME,
                ): vol.In(SUPPORTED_COUNTRY_NAMES),
                vol.Required(CONF_USERNAME, default=vol.UNDEFINED): str,
                vol.Required(CONF_PASSWORD, default=vol.UNDEFINED): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
