"""Config flow for NRGkick integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
import yarl

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    NRGkickAPI,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _normalize_host(value: str) -> str:
    """Normalize user input to host[:port] (no scheme/path).

    Accepts either a plain host/IP (optionally with a port) or a full URL.
    If a URL is provided, we strip the scheme.
    """

    value = value.strip()
    if not value:
        raise vol.Invalid("host is required")
    if "://" in value:
        url = yarl.URL(cv.url(value))
        if not url.host:
            raise vol.Invalid("invalid url")
        if url.port is not None:
            return f"{url.host}:{url.port}"
        return url.host
    return value.strip("/").split("/", 1)[0]


HOST_SCHEMA = vol.All(cv.string, _normalize_host)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): HOST_SCHEMA})


STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: HomeAssistant,
    host: str,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    api = NRGkickAPI(
        host=host,
        username=username,
        password=password,
        session=session,
    )

    await api.test_connection()

    info = await api.get_info(["general"])
    device_name = info.get("general", {}).get("device_name")
    if not device_name:
        device_name = "NRGkick"

    serial = info.get("general", {}).get("serial_number")
    if not serial:
        raise ValueError

    return {
        "title": device_name,
        "serial": serial,
    }


class NRGkickConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NRGkick."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._pending_host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]

            try:
                info = await validate_input(self.hass, host)
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                self._pending_host = host
                return await self.async_step_user_auth()
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["serial"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"], data={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_ip": user_input[CONF_HOST] if user_input else "",
            },
        )

    async def async_step_user_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step only when needed."""
        errors: dict[str, str] = {}

        if not self._pending_host:
            return await self.async_step_user()

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            try:
                info = await validate_input(
                    self.hass,
                    self._pending_host,
                    username=username,
                    password=password,
                )
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["serial"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: self._pending_host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user_auth",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_ip": self._pending_host,
            },
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered NRGkick device: %s", discovery_info)

        # Extract device information from mDNS metadata.
        serial = discovery_info.properties.get("serial_number")
        device_name = discovery_info.properties.get("device_name")
        model_type = discovery_info.properties.get("model_type")
        json_api_enabled = discovery_info.properties.get("json_api_enabled", "0")

        if not serial:
            _LOGGER.debug("NRGkick device discovered without serial number")
            return self.async_abort(reason="no_serial_number")

        # Set unique ID to prevent duplicate entries.
        await self.async_set_unique_id(serial)
        # Update the host if the device is already configured (IP might have changed).
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        # Store discovery info for the confirmation step.
        self._discovered_host = discovery_info.host
        # Fallback: device_name -> model_type -> "NRGkick".
        self._discovered_name = device_name or model_type or "NRGkick"
        self.context["title_placeholders"] = {
            "name": self._discovered_name or "NRGkick"
        }

        # If JSON API is disabled, guide the user through enabling it.
        if json_api_enabled != "1":
            _LOGGER.debug("NRGkick device %s does not have JSON API enabled", serial)
            return await self.async_step_zeroconf_enable_json_api()

        # Proceed to confirmation step (no auth required upfront).
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_enable_json_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Guide the user to enable JSON API after discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _normalize_host(self._discovered_host or "")

            try:
                info = await validate_input(self.hass, host)
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                self._pending_host = host
                return await self.async_step_zeroconf_enable_json_api_auth()
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"], data={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="zeroconf_enable_json_api",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._discovered_name or "NRGkick",
                "device_ip": _normalize_host(self._discovered_host or ""),
            },
            errors=errors,
        )

    async def async_step_zeroconf_enable_json_api_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication after JSON API enabling guidance."""
        errors: dict[str, str] = {}

        if not self._pending_host:
            return await self.async_step_zeroconf_enable_json_api()

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            try:
                info = await validate_input(
                    self.hass,
                    self._pending_host,
                    username=username,
                    password=password,
                )
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: self._pending_host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_enable_json_api_auth",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            description_placeholders={
                "name": self._discovered_name or "NRGkick",
                "device_ip": self._pending_host,
            },
            errors=errors,
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _normalize_host(self._discovered_host or "")

            try:
                info = await validate_input(self.hass, host)
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                self._pending_host = host
                return await self.async_step_zeroconf_auth()
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"], data={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._discovered_name or "NRGkick",
                "device_ip": _normalize_host(self._discovered_host or ""),
            },
            errors=errors,
        )

    async def async_step_zeroconf_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication for zeroconf discovery when needed."""
        errors: dict[str, str] = {}

        if not self._pending_host:
            return await self.async_step_zeroconf_confirm()

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            try:
                info = await validate_input(
                    self.hass,
                    self._pending_host,
                    username=username,
                    password=password,
                )
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: self._pending_host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_auth",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            description_placeholders={
                "name": self._discovered_name or "NRGkick",
                "device_ip": self._pending_host,
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="reauth_failed")

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        if user_input is not None:
            data = {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            try:
                await validate_input(
                    self.hass,
                    data[CONF_HOST],
                    username=data.get(CONF_USERNAME),
                    password=data.get(CONF_PASSWORD),
                )
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data=data, reason="reauth_successful"
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": entry.data[CONF_HOST],
                "device_ip": _normalize_host(entry.data[CONF_HOST]),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_reconfigure_confirm(user_input)

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration confirmation."""
        errors: dict[str, str] = {}
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="reconfigure_failed")

        entry = self.hass.config_entries.async_get_entry(entry_id)

        if entry is None:
            return self.async_abort(reason="reconfigure_failed")

        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            try:
                await validate_input(
                    self.hass,
                    data[CONF_HOST],
                    username=data.get(CONF_USERNAME),
                    password=data.get(CONF_PASSWORD),
                )
            except ValueError:
                errors["base"] = "no_serial_number"
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error during reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data=data, reason="reconfigure_successful"
                )

        host = entry.data.get(CONF_HOST, "")
        username = entry.data.get(CONF_USERNAME) or ""
        password = entry.data.get(CONF_PASSWORD) or ""

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): HOST_SCHEMA,
                    vol.Optional(CONF_USERNAME, default=username): str,
                    vol.Optional(CONF_PASSWORD, default=password): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": host,
                "device_ip": user_input[CONF_HOST] if user_input else host,
            },
        )
