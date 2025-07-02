"""Config flow for Alexa Devices integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aioamazondevices.api import AmazonEchoApi
from aioamazondevices.exceptions import CannotAuthenticate, CannotConnect, WrongCountry
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import CountrySelector

from .const import CONF_LOGIN_DATA, DOMAIN

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CODE): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    api = AmazonEchoApi(
        data[CONF_COUNTRY],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )

    try:
        data = await api.login_mode_interactive(data[CONF_CODE])
    finally:
        await api.close()

    return data


class AmazonDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alexa Devices."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input:
            try:
                data = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            except WrongCountry:
                errors["base"] = "wrong_country"
            else:
                await self.async_set_unique_id(data["customer_info"]["user_id"])
                self._abort_if_unique_id_configured()
                user_input.pop(CONF_CODE)
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input | {CONF_LOGIN_DATA: data},
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COUNTRY, default=self.hass.config.country
                    ): CountrySelector(),
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_CODE): cv.string,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        self.context["title_placeholders"] = {CONF_USERNAME: entry_data[CONF_USERNAME]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        entry_data = reauth_entry.data

        if user_input is not None:
            try:
                await validate_input(self.hass, {**reauth_entry.data, **user_input})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_USERNAME: entry_data[CONF_USERNAME],
                        CONF_PASSWORD: entry_data[CONF_PASSWORD],
                        CONF_CODE: user_input[CONF_CODE],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_USERNAME: entry_data[CONF_USERNAME]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
