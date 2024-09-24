"""Config flow for Frontier Silicon Media Player integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

from afsapi import (
    AFSAPI,
    ConnectionError as FSConnectionError,
    InvalidPinException,
    NotImplementedException,
)
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT

from .const import (
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


def hostname_from_url(url: str) -> str:
    """Return the hostname from a url."""
    return str(urlparse(url).hostname)


class FrontierSiliconConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Frontier Silicon Media Player."""

    VERSION = 1

    _name: str
    _webfsapi_url: str
    _reauth_entry: ConfigEntry | None = None  # Only used in reauth flows

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._async_step_device_config_if_needed()

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, user_input
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Process entity discovered via SSDP."""

        device_url = discovery_info.ssdp_location
        if device_url is None:
            return self.async_abort(reason="cannot_connect")

        device_hostname = hostname_from_url(device_url)
        for entry in self._async_current_entries(include_ignore=False):
            if device_hostname == hostname_from_url(entry.data[CONF_WEBFSAPI_URL]):
                return self.async_abort(reason="already_configured")

        speaker_name = discovery_info.ssdp_headers.get(SSDP_ATTR_SPEAKER_NAME)
        self.context["title_placeholders"] = {"name": speaker_name}

        try:
            self._webfsapi_url = await AFSAPI.get_webfsapi_endpoint(device_url)
        except FSConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception as exception:  # noqa: BLE001
            _LOGGER.debug(exception)
            return self.async_abort(reason="unknown")

        # try to login with default pin
        afsapi = AFSAPI(self._webfsapi_url, DEFAULT_PIN)
        try:
            await afsapi.get_friendly_name()
        except InvalidPinException:
            return self.async_abort(reason="invalid_auth")

        try:
            unique_id = await afsapi.get_radio_id()
        except NotImplementedException:
            unique_id = None

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_WEBFSAPI_URL: self._webfsapi_url}, reload_on_update=True
        )

        self._name = await afsapi.get_friendly_name()

        return await self.async_step_confirm()

    async def _async_step_device_config_if_needed(self) -> ConfigFlowResult:
        """Most users will not have changed the default PIN on their radio.

        We try to use this default PIN, and only if this fails ask for it via `async_step_device_config`
        """

        try:
            # try to login with default pin
            afsapi = AFSAPI(self._webfsapi_url, DEFAULT_PIN)

            self._name = await afsapi.get_friendly_name()
        except InvalidPinException:
            # Ask for a PIN
            return await self.async_step_device_config()

        self.context["title_placeholders"] = {"name": self._name}

        try:
            unique_id = await afsapi.get_radio_id()
        except NotImplementedException:
            unique_id = None
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return await self._async_create_entry()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device. Used when the default PIN could successfully be used."""

        if user_input is not None:
            return await self._async_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": self._name}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._webfsapi_url = entry_data[CONF_WEBFSAPI_URL]

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_device_config()

    async def async_step_device_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device configuration step.

        We ask for the PIN in this step.
        """

        if user_input is None:
            return self.async_show_form(
                step_id="device_config", data_schema=STEP_DEVICE_CONFIG_DATA_SCHEMA
            )

        errors = {}

        try:
            afsapi = AFSAPI(self._webfsapi_url, user_input[CONF_PIN])

            self._name = await afsapi.get_friendly_name()

        except FSConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidPinException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if self._reauth_entry:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={CONF_PIN: user_input[CONF_PIN]},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            try:
                unique_id = await afsapi.get_radio_id()
            except NotImplementedException:
                unique_id = None
            await self.async_set_unique_id(unique_id, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self._async_create_entry(user_input[CONF_PIN])

        data_schema = self.add_suggested_values_to_schema(
            STEP_DEVICE_CONFIG_DATA_SCHEMA, user_input
        )
        return self.async_show_form(
            step_id="device_config",
            data_schema=data_schema,
            errors=errors,
        )

    async def _async_create_entry(self, pin: str | None = None):
        """Create the entry."""

        return self.async_create_entry(
            title=self._name,
            data={CONF_WEBFSAPI_URL: self._webfsapi_url, CONF_PIN: pin or DEFAULT_PIN},
        )
