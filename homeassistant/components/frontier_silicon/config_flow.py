"""Config flow for Frontier Silicon Media Player integration."""
from __future__ import annotations

import logging
from typing import Any

from afsapi import AFSAPI, ConnectionError as FSConnectionError, InvalidPinException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_PIN, CONF_WEBFSAPI_URL, DEFAULT_PIN, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

STEP_DEVICE_CONFIG_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_PIN,
            default=DEFAULT_PIN,
        ): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Frontier Silicon Media Player."""

    VERSION = 1

    _webfsapi_url: str

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Handle the import of legacy configuration.yaml entries."""

        device_url = f"http://{import_info[CONF_HOST]}:{import_info[CONF_PORT]}/device"
        try:
            self._webfsapi_url = await AFSAPI.get_webfsapi_endpoint(device_url)
        except FSConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            return self.async_abort(reason="unknown")

        try:
            afsapi = AFSAPI(self._webfsapi_url, import_info[CONF_PIN])

            unique_id = await afsapi.get_radio_id()
        except FSConnectionError:
            return self.async_abort(reason="cannot_connect")
        except InvalidPinException:
            return self.async_abort(reason="invalid_auth")
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_info[CONF_NAME] or "Radio",
            data={
                CONF_WEBFSAPI_URL: self._webfsapi_url,
                CONF_PIN: import_info[CONF_PIN],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of manual configuration."""
        errors = {}

        if user_input:
            device_url = (
                f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/device"
            )
            try:
                self._webfsapi_url = await AFSAPI.get_webfsapi_endpoint(device_url)
            except FSConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                return await self._async_step_device_config_if_needed()

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, user_input
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def _async_step_device_config_if_needed(self) -> FlowResult:
        """Most users will not have changed the default PIN on their radio.

        We try to use this default PIN, and only if this fails ask for it via `async_step_device_config`
        """

        try:
            # try to login with default pin
            afsapi = AFSAPI(self._webfsapi_url, DEFAULT_PIN)

            name = await afsapi.get_friendly_name()
        except InvalidPinException:
            # Ask for a PIN
            return await self.async_step_device_config()

        self.context["title_placeholders"] = {"name": name}

        unique_id = await afsapi.get_radio_id()
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data={CONF_WEBFSAPI_URL: self._webfsapi_url, CONF_PIN: DEFAULT_PIN},
        )

    async def async_step_device_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device configuration step.

        We ask for the PIN in this step.
        """
        assert self._webfsapi_url is not None

        if user_input is None:
            return self.async_show_form(
                step_id="device_config", data_schema=STEP_DEVICE_CONFIG_DATA_SCHEMA
            )

        errors = {}

        try:
            afsapi = AFSAPI(self._webfsapi_url, user_input[CONF_PIN])

            name = await afsapi.get_friendly_name()

        except FSConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidPinException:
            errors["base"] = "invalid_auth"
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            errors["base"] = "unknown"
        else:
            unique_id = await afsapi.get_radio_id()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name,
                data={
                    CONF_WEBFSAPI_URL: self._webfsapi_url,
                    CONF_PIN: user_input[CONF_PIN],
                },
            )

        data_schema = self.add_suggested_values_to_schema(
            STEP_DEVICE_CONFIG_DATA_SCHEMA, user_input
        )
        return self.async_show_form(
            step_id="device_config",
            data_schema=data_schema,
            errors=errors,
        )
