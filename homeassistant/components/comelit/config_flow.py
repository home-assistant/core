"""Config flow for Comelit integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiocomelit import (
    ComeliteSerialBridgeApi,
    ComelitVedoApi,
    exceptions as aiocomelit_exceptions,
)
from aiocomelit.api import ComelitCommonApi
from aiocomelit.const import BRIDGE
import voluptuous as vol

from homeassistant import core, exceptions
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import _LOGGER, DEFAULT_PORT, DEVICE_TYPE_LIST, DOMAIN

DEFAULT_HOST = "192.168.1.252"
DEFAULT_PIN = 111111


def user_form_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Return user form schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
            vol.Required(CONF_TYPE, default=BRIDGE): vol.In(DEVICE_TYPE_LIST),
        }
    )


STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PIN): cv.positive_int})


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    api: ComelitCommonApi
    if data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        api = ComeliteSerialBridgeApi(data[CONF_HOST], data[CONF_PORT], data[CONF_PIN])
    else:
        api = ComelitVedoApi(data[CONF_HOST], data[CONF_PORT], data[CONF_PIN])

    try:
        await api.login()
    except aiocomelit_exceptions.CannotConnect as err:
        raise CannotConnect from err
    except aiocomelit_exceptions.CannotAuthenticate as err:
        raise InvalidAuth from err
    finally:
        await api.logout()
        await api.close()

    return {"title": data[CONF_HOST]}


class ComelitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comelit."""

    VERSION = 1
    _reauth_entry: ConfigEntry | None
    _reauth_host: str
    _reauth_port: int
    _reauth_type: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=user_form_schema(user_input)
            )

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=user_form_schema(user_input), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._reauth_host = entry_data[CONF_HOST]
        self._reauth_port = entry_data.get(CONF_PORT, DEFAULT_PORT)
        self._reauth_type = entry_data.get(CONF_TYPE, BRIDGE)

        self.context["title_placeholders"] = {"host": self._reauth_host}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirm."""
        assert self._reauth_entry
        errors = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    {
                        CONF_HOST: self._reauth_host,
                        CONF_PORT: self._reauth_port,
                        CONF_TYPE: self._reauth_type,
                    }
                    | user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        CONF_HOST: self._reauth_host,
                        CONF_PORT: self._reauth_port,
                        CONF_PIN: user_input[CONF_PIN],
                        CONF_TYPE: self._reauth_type,
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_HOST: self._reauth_entry.data[CONF_HOST]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
