"""Config flow for Comelit integration."""

from __future__ import annotations

from asyncio.exceptions import TimeoutError
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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import _LOGGER, DEFAULT_PORT, DEVICE_TYPE_LIST, DOMAIN
from .utils import async_client_session

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


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    api: ComelitCommonApi

    session = await async_client_session(hass)
    if data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        api = ComeliteSerialBridgeApi(
            data[CONF_HOST], data[CONF_PORT], data[CONF_PIN], session
        )
    else:
        api = ComelitVedoApi(data[CONF_HOST], data[CONF_PORT], data[CONF_PIN], session)

    try:
        await api.login()
    except (aiocomelit_exceptions.CannotConnect, TimeoutError) as err:
        raise CannotConnect(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": repr(err)},
        ) from err
    except aiocomelit_exceptions.CannotAuthenticate as err:
        raise InvalidAuth(
            translation_domain=DOMAIN,
            translation_key="cannot_authenticate",
            translation_placeholders={"error": repr(err)},
        ) from err
    finally:
        await api.logout()
        await api.close()

    return {"title": data[CONF_HOST]}


class ComelitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comelit."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=user_form_schema(user_input), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        self.context["title_placeholders"] = {"host": entry_data[CONF_HOST]}
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
                await validate_input(
                    self.hass,
                    {
                        CONF_HOST: entry_data[CONF_HOST],
                        CONF_PORT: entry_data.get(CONF_PORT, DEFAULT_PORT),
                        CONF_TYPE: entry_data.get(CONF_TYPE, BRIDGE),
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
                        CONF_HOST: entry_data[CONF_HOST],
                        CONF_PORT: entry_data.get(CONF_PORT, DEFAULT_PORT),
                        CONF_PIN: user_input[CONF_PIN],
                        CONF_TYPE: entry_data.get(CONF_TYPE, BRIDGE),
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_HOST: entry_data[CONF_HOST]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
