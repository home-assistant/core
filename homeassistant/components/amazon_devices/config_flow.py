"""Config flow for Amazon Devices integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aioamazondevices
from aioamazondevices import AmazonEchoApi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import _LOGGER, CONF_LOGIN_DATA, DEFAULT_COUNTRY, DOMAIN


def user_form_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Return user form schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): cv.country,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_CODE): cv.positive_int,
        }
    )


STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CODE): cv.positive_int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    api = AmazonEchoApi(data[CONF_COUNTRY], data[CONF_USERNAME], data[CONF_PASSWORD])

    try:
        login_data = await api.login_mode_interactive(data[CONF_CODE])

    except aioamazondevices.exceptions.CannotConnect as err:
        raise CannotConnect from err
    except aioamazondevices.exceptions.CannotAuthenticate as err:
        raise InvalidAuth from err
    finally:
        await api.close()

    return {"title": data[CONF_USERNAME], CONF_LOGIN_DATA: login_data}


class AmazonDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amazon Devices."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=user_form_schema(user_input)
            )

        self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"],
                data=user_input | {CONF_LOGIN_DATA: info[CONF_LOGIN_DATA]},
            )

        return self.async_show_form(
            step_id="user", data_schema=user_form_schema(user_input), errors=errors
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
        errors = {}

        reauth_entry = self._get_reauth_entry()
        entry_data = reauth_entry.data

        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass,
                    {
                        CONF_COUNTRY: entry_data[CONF_COUNTRY],
                        CONF_USERNAME: entry_data.get(CONF_USERNAME),
                        CONF_PASSWORD: entry_data.get(CONF_PASSWORD),
                        CONF_CODE: entry_data.get(CONF_CODE),
                    }
                    | user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_COUNTRY: entry_data[CONF_COUNTRY],
                        CONF_USERNAME: entry_data.get(CONF_USERNAME),
                        CONF_PASSWORD: entry_data.get(CONF_PASSWORD),
                        CONF_CODE: entry_data.get(CONF_CODE),
                        CONF_LOGIN_DATA: info[CONF_LOGIN_DATA],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_USERNAME: entry_data[CONF_USERNAME]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
