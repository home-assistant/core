"""Config flow for NRGkick integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nrgkick_api import NRGkickAPI
import voluptuous as vol
import yarl

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    NRGkickApiClientApiDisabledError,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
    NRGkickApiClientInvalidResponseError,
    async_api_call,
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
        try:
            url = yarl.URL(cv.url(value))
        except ValueError as err:
            raise vol.Invalid("invalid url") from err
        if not url.host:
            raise vol.Invalid("invalid url")
        if url.port is not None:
            return f"{url.host}:{url.port}"
        return url.host
    return value.strip("/").split("/", 1)[0]


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(autocomplete="off")),
    }
)


STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(autocomplete="off")
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
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

    await async_api_call(api.test_connection())
    info = await async_api_call(api.get_info(["general"], raw=True))

    device_name = info.get("general", {}).get("device_name")
    if not device_name:
        device_name = "NRGkick"

    serial = info.get("general", {}).get("serial_number")
    if not serial:
        raise NRGkickApiClientInvalidResponseError

    return {
        "title": device_name,
        "serial": serial,
    }


class NRGkickConfigFlow(ConfigFlow, domain=DOMAIN):
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
            try:
                host = _normalize_host(user_input[CONF_HOST])
            except vol.Invalid:
                errors["base"] = "cannot_connect"
            else:
                try:
                    info = await validate_input(self.hass, host)
                except NRGkickApiClientApiDisabledError:
                    errors["base"] = "json_api_disabled"
                except NRGkickApiClientAuthenticationError:
                    self._pending_host = host
                    return await self.async_step_user_auth()
                except NRGkickApiClientInvalidResponseError:
                    errors["base"] = "invalid_response"
                except NRGkickApiClientCommunicationError:
                    errors["base"] = "cannot_connect"
                except NRGkickApiClientError:
                    _LOGGER.exception("Unexpected error")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(
                        info["serial"], raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info["title"], data={CONF_HOST: host}
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step only when needed."""
        errors: dict[str, str] = {}

        if TYPE_CHECKING:
            assert self._pending_host is not None

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
            except NRGkickApiClientApiDisabledError:
                errors["base"] = "json_api_disabled"
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientInvalidResponseError:
                errors["base"] = "invalid_response"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["serial"], raise_on_progress=False)
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
        self.context["title_placeholders"] = {"name": self._discovered_name}

        # If JSON API is disabled, guide the user through enabling it.
        if json_api_enabled != "1":
            _LOGGER.debug("NRGkick device %s does not have JSON API enabled", serial)
            return await self.async_step_zeroconf_enable_json_api()

        try:
            await validate_input(self.hass, self._discovered_host)
        except NRGkickApiClientAuthenticationError:
            self._pending_host = self._discovered_host
            return await self.async_step_user_auth()
        except NRGkickApiClientApiDisabledError:
            # mDNS metadata may be stale; fall back to the enable guidance.
            return await self.async_step_zeroconf_enable_json_api()
        except (
            NRGkickApiClientCommunicationError,
            NRGkickApiClientInvalidResponseError,
        ):
            return self.async_abort(reason="cannot_connect")
        except NRGkickApiClientError:
            _LOGGER.exception("Unexpected error")
            return self.async_abort(reason="unknown")

        # Proceed to confirmation step (no auth required upfront).
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_enable_json_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Guide the user to enable JSON API after discovery."""
        errors: dict[str, str] = {}

        if TYPE_CHECKING:
            assert self._discovered_host is not None
            assert self._discovered_name is not None

        if user_input is not None:
            try:
                info = await validate_input(self.hass, self._discovered_host)
            except NRGkickApiClientApiDisabledError:
                errors["base"] = "json_api_disabled"
            except NRGkickApiClientAuthenticationError:
                self._pending_host = self._discovered_host
                return await self.async_step_user_auth()
            except NRGkickApiClientInvalidResponseError:
                errors["base"] = "invalid_response"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except NRGkickApiClientError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"], data={CONF_HOST: self._discovered_host}
                )

        return self.async_show_form(
            step_id="zeroconf_enable_json_api",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._discovered_name,
                "device_ip": _normalize_host(self._discovered_host),
            },
            errors=errors,
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}

        if TYPE_CHECKING:
            assert self._discovered_host is not None
            assert self._discovered_name is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name, data={CONF_HOST: self._discovered_host}
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._discovered_name,
                "device_ip": self._discovered_host,
            },
            errors=errors,
        )
