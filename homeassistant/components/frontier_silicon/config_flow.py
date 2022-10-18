"""Config flow for Frontier Silicon Media Player integration."""
from __future__ import annotations

import logging
from typing import Any

from afsapi import AFSAPI, ConnectionError as FSConnectionError, InvalidPinException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_PIN,
    CONF_WEBFSAPI_URL,
    DEFAULT_PIN,
    DEFAULT_PORT,
    DOMAIN,
    SSDP_ATTR_SPEAKER_NAME,
)

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

    def __init__(self) -> None:
        """Initialize flow."""

        self._webfsapi_url: str | None = None
        self._name: str | None = None
        self._unique_id: str | None = None

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

            self._unique_id = await afsapi.get_radio_id()
        except FSConnectionError:
            return self.async_abort(reason="cannot_connect")
        except InvalidPinException:
            return self.async_abort(reason="invalid_auth")
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            return self.async_abort(reason="unknown")

        # For manually added devices the unique_id is the radio_id,
        # for devices discovered through SSDP it is the UDN
        await self.async_set_unique_id(self._unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        self._name = import_info[CONF_NAME] or "Radio"

        _LOGGER.warning("Frontier Silicon %s imported from YAML config", self._name)
        return await self._create_entry(pin=import_info[CONF_PIN])

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of manual configuration."""
        errors = {}
        if user_input is not None:

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

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Process entity discovered via SSDP."""

        device_url = discovery_info.ssdp_location

        speaker_name = discovery_info.ssdp_headers.get(SSDP_ATTR_SPEAKER_NAME)
        self.context["title_placeholders"] = {"name": speaker_name}

        try:
            self._webfsapi_url = await AFSAPI.get_webfsapi_endpoint(device_url)
        except FSConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            return self.async_abort(reason="unknown")

        # For manually added devices the unique_id is the radio_id,
        # for devices discovered through SSDP it is the UDN
        self._unique_id = discovery_info.ssdp_udn
        await self.async_set_unique_id(self._unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_WEBFSAPI_URL: self._webfsapi_url}, reload_on_update=True
        )

        return await self._async_step_device_config_if_needed(show_confirm=True)

    async def _async_step_device_config_if_needed(
        self, show_confirm=False
    ) -> FlowResult:
        """Most users will not have changed the default PIN on their radio.

        We try to use this default PIN, and only if this fails ask for it via `async_step_device_config`
        """

        try:
            # try to login with default pin
            afsapi = AFSAPI(self._webfsapi_url, DEFAULT_PIN)

            self._name = await afsapi.get_friendly_name()

            self.context["title_placeholders"] = {"name": self._name}

            # _unique_id will already be set when discovered through SSDP with the SSDP UDN,
            # however, when adding a device manually, it will still be empty at this point.
            # Now we have successfully logged in, we can check the radio_id of this device
            if self._unique_id is None:
                self._unique_id = await afsapi.get_radio_id()
                await self.async_set_unique_id(self._unique_id)
                self._abort_if_unique_id_configured()

            if show_confirm:
                return await self.async_step_confirm()

            return await self._create_entry()
        except InvalidPinException:
            pass  # Ask for a PIN

        return await self.async_step_device_config()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device. Used when the default PIN could successfully be used."""

        if user_input is not None:
            return await self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

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

            self._name = await afsapi.get_friendly_name()

            # _unique_id will already be set when discovered through SSDP with the SSDP UDN,
            # however, when adding a device manually, it will still be empty at this point.
            # Now we have successfully logged in, we can check the radio_id of this device
            if self._unique_id is None:
                self._unique_id = await afsapi.get_radio_id()
                await self.async_set_unique_id(self._unique_id)
                self._abort_if_unique_id_configured()

        except FSConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidPinException:
            errors["base"] = "invalid_auth"
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            errors["base"] = "unknown"
        else:
            return await self._create_entry(pin=user_input[CONF_PIN])

        return self.async_show_form(
            step_id="device_config",
            data_schema=STEP_DEVICE_CONFIG_DATA_SCHEMA,
            errors=errors,
        )

    async def _create_entry(self, pin: str | None = None) -> FlowResult:
        """Create the entry."""
        assert self._name is not None
        assert self._webfsapi_url is not None

        data = {CONF_WEBFSAPI_URL: self._webfsapi_url, CONF_PIN: pin or DEFAULT_PIN}

        return self.async_create_entry(title=self._name, data=data)
