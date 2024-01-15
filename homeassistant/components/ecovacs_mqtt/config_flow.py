"""Config flow for Ecovacs mqtt integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientError
from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator
from deebot_client.exceptions import InvalidAuthenticationError
from deebot_client.models import Configuration, DeviceInfo
from deebot_client.util import md5
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_DEVICES,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, selector

from .const import CONF_COUNTRY, DOMAIN, SELF_HOSTED_CONFIGURATION, Mode
from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


class EcovacsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecovacs."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._devices: list[DeviceInfo] = []
        self._entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> EcovacsOptionsFlowHandler:
        """Get the options flow for this handler."""
        return EcovacsOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if not self.show_advanced_options:
            self._data[CONF_MODE] = Mode.CLOUD
            return await self.async_step_auth()

        if user_input:
            self._data.update(user_input)
            auth_input = None
            if user_input[CONF_MODE] == Mode.SELF_HOSTED:
                auth_input = SELF_HOSTED_CONFIGURATION.copy()

            return await self.async_step_auth(user_input=auth_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODE, default=Mode.CLOUD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            translation_key="mode", options=list(Mode)
                        )
                    )
                }
            ),
        )

    async def async_step_auth(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Handle the auth step."""
        errors = {}

        if user_input is not None:
            try:
                self._devices = await _retrieve_devices(self.hass, user_input)
            except ClientError:
                _LOGGER.debug("Cannot connect", exc_info=True)
                errors["base"] = "cannot_connect"
            except InvalidAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                self._data.update(user_input)
                if self._entry:
                    # reauthentication
                    self.hass.config_entries.async_update_entry(
                        self._entry, data=self._data
                    )
                    return self.async_abort(reason="reauth_successful")

                self._async_abort_entries_match(
                    {CONF_USERNAME: user_input[CONF_USERNAME]}
                )

                if len(self._devices) == 0:
                    return self.async_abort(reason="no_supported_devices_found")

                return await self.async_step_options()

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.TEXT
                            )
                        ),
                        vol.Required(CONF_PASSWORD): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD
                            )
                        ),
                        vol.Required(CONF_COUNTRY): selector.CountrySelector(),
                    }
                ),
                user_input or {CONF_COUNTRY: self.hass.config.country},
            ),
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""

        errors = {}
        if user_input is not None:
            if len(user_input[CONF_DEVICES]) < 1:
                errors[CONF_DEVICES] = "select_robots"
            else:
                return self.async_create_entry(
                    title=self._data[CONF_USERNAME],
                    data=self._data,
                    options=user_input,
                )

        return self.async_show_form(
            step_id="options",
            data_schema=_get_options_schema(self._devices, {}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._data = dict(entry_data)
        return await self.async_step_auth(entry_data)


def _get_options_schema(
    devices: list[DeviceInfo], defaults: Mapping[str, Any]
) -> vol.Schema:
    """Return options schema."""
    select_options = []

    for entry in devices:
        api_info = entry.api_device_info
        name = api_info["name"]
        label = api_info.get("nick", name)
        select_options.append(selector.SelectOptionDict(value=name, label=label))

    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICES, default=defaults.get(CONF_DEVICES, vol.UNDEFINED)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=select_options,
                    multiple=True,
                )
            )
        }
    )


async def _retrieve_devices(
    hass: HomeAssistant, integration_config: Mapping[str, Any]
) -> list[DeviceInfo]:
    verify_ssl = integration_config.get(CONF_VERIFY_SSL, True)
    deebot_config = Configuration(
        aiohttp_client.async_get_clientsession(hass, verify_ssl=verify_ssl),
        device_id=get_client_device_id(hass, integration_config[CONF_MODE]),
        country=integration_config[CONF_COUNTRY],
        verify_ssl=verify_ssl,
    )

    authenticator = Authenticator(
        deebot_config,
        integration_config[CONF_USERNAME],
        md5(integration_config[CONF_PASSWORD]),
    )
    api_client = ApiClient(authenticator)

    return await api_client.get_devices()


class EcovacsOptionsFlowHandler(OptionsFlow):
    """Handle ecovacs options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._devices: list[DeviceInfo] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors = {}
        if user_input is not None:
            try:
                if len(user_input[CONF_DEVICES]) < 1:
                    errors[CONF_DEVICES] = "select_robots"
                else:
                    return self.async_create_entry(
                        title=self._config_entry.title,
                        data=user_input,
                    )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        if not self._devices:
            try:
                self._devices = await _retrieve_devices(
                    self.hass, self._config_entry.data
                )
            except ClientError:
                _LOGGER.debug("Cannot connect", exc_info=True)
                return self.async_abort(reason="cannot_connect")
            except InvalidAuthenticationError:
                return self.async_abort(reason="invalid_auth")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception on getting devices")
                return self.async_abort(reason="unknown_get_devices")

            if len(self._devices) == 0:
                return self.async_abort(reason="no_supported_devices_found")

        return self.async_show_form(
            step_id="init",
            data_schema=_get_options_schema(
                self._devices, user_input or self._config_entry.options
            ),
            errors=errors,
        )
