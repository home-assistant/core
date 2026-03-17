"""Config flow for Comelit integration."""

from __future__ import annotations

from asyncio.exceptions import TimeoutError
from collections.abc import Mapping
import re
from typing import TYPE_CHECKING, Any

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

from .const import _LOGGER, CONF_VEDO_PIN, DEFAULT_PORT, DEVICE_TYPE_LIST, DOMAIN
from .utils import async_client_session

DEFAULT_HOST = "192.168.1.252"
DEFAULT_PIN = "111111"

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.string,
        vol.Required(CONF_TYPE, default=BRIDGE): vol.In(DEVICE_TYPE_LIST),
        vol.Optional(CONF_VEDO_PIN): cv.string,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_PIN): cv.string, vol.Optional(CONF_VEDO_PIN): cv.string}
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    api: ComelitCommonApi

    if not re.fullmatch(r"[0-9]{4,10}", data[CONF_PIN]):
        raise InvalidPin

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

    # Validate VEDO PIN if provided and device type is BRIDGE
    if data.get(CONF_VEDO_PIN) and data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        if not re.fullmatch(r"[0-9]{4,10}", data[CONF_VEDO_PIN]):
            raise InvalidVedoPin

        if TYPE_CHECKING:
            assert isinstance(api, ComeliteSerialBridgeApi)

        # Verify VEDO is enabled with the provided PIN
        if not await api.vedo_enabled(data[CONF_VEDO_PIN]):
            raise InvalidVedoAuth

    return {"title": data[CONF_HOST]}


class ComelitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comelit."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        errors: dict[str, str] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidPin:
            errors["base"] = "invalid_pin"
        except InvalidVedoPin:
            errors["base"] = "invalid_vedo_pin"
        except InvalidVedoAuth:
            errors["base"] = "invalid_vedo_auth"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        self.context["title_placeholders"] = {CONF_HOST: entry_data[CONF_HOST]}
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
            except InvalidPin:
                errors["base"] = "invalid_pin"
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            updated_host = user_input[CONF_HOST]

            self._async_abort_entries_match({CONF_HOST: updated_host})

            try:
                data_to_validate = {
                    CONF_HOST: updated_host,
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_PIN: user_input[CONF_PIN],
                    CONF_TYPE: reconfigure_entry.data.get(CONF_TYPE, BRIDGE),
                }
                if CONF_VEDO_PIN in user_input:
                    data_to_validate[CONF_VEDO_PIN] = user_input[CONF_VEDO_PIN]
                await validate_input(self.hass, data_to_validate)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidPin:
                errors["base"] = "invalid_pin"
            except InvalidVedoPin:
                errors["base"] = "invalid_vedo_pin"
            except InvalidVedoAuth:
                errors["base"] = "invalid_vedo_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data_updates = {
                    CONF_HOST: updated_host,
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_PIN: user_input[CONF_PIN],
                }
                if CONF_VEDO_PIN in user_input:
                    data_updates[CONF_VEDO_PIN] = user_input[CONF_VEDO_PIN]
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=data_updates
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=reconfigure_entry.data[CONF_HOST]
                ): cv.string,
                vol.Required(
                    CONF_PORT, default=reconfigure_entry.data[CONF_PORT]
                ): cv.port,
                vol.Optional(CONF_PIN): cv.string,
                vol.Optional(CONF_VEDO_PIN): cv.string,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidPin(HomeAssistantError):
    """Error to indicate an invalid pin."""


class InvalidVedoPin(HomeAssistantError):
    """Error to indicate an invalid VEDO pin."""


class InvalidVedoAuth(HomeAssistantError):
    """Error to indicate VEDO authentication failed."""
