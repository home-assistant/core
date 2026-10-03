"""Config flow for the AirLino integration."""

import logging
from typing import override

import aiohttp
from probatio import Optional, Schema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import AirlinoApi, AirlinoApiConnectionError, AirlinoApiError
from .const import (
    DEFAULT_API_VERSION,
    DEFAULT_PORT,
    DOMAIN,
    MIN_API_VERSION,
    VALID_MODELS,
    api_version_number,
    is_supported_api_version,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = Schema(
    {
        "host": str,
        Optional("port", default=DEFAULT_PORT): int,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict, api_version: str | None = None
) -> dict:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    if api_version is None:
        latest_version = api_version_number(DEFAULT_API_VERSION)
        minimum_version = api_version_number(MIN_API_VERSION)
        if latest_version is None or minimum_version is None:
            raise UnsupportedApiVersion
        versions = [
            f"v{version}" for version in range(latest_version, minimum_version - 1, -1)
        ]
    else:
        versions = [api_version]

    for version in versions:
        if not is_supported_api_version(version):
            raise UnsupportedApiVersion
        api = AirlinoApi(
            host=data[CONF_HOST],
            port=data.get("port", DEFAULT_PORT),
            api_version=version,
            session=session,
        )
        try:
            device_info = await api.async_get_device_info()
            network_info = await api.async_get_network_info()
        except AirlinoApiError as err:
            if api_version is None and err.status in (None, 404):
                continue
            if err.status == 404:
                raise UnsupportedApiVersion from err
            raise CannotConnect from err
        except (AirlinoApiConnectionError, aiohttp.ClientError) as err:
            raise CannotConnect from err

        mac = _get_mac(network_info)
        if not mac:
            if api_version is None:
                continue
            raise CannotIdentify

        return {
            "title": device_info.get("devicename", "AirLino"),
            "mac": mac,
            "api_version": version,
        }

    raise UnsupportedApiVersion


def _get_mac(network_info: dict) -> str | None:
    """Extract a MAC address from the network info (eth preferred, then wlan)."""
    for iface in ("eth", "wlan"):
        interface = network_info.get(iface)
        if interface and interface.get("mac"):
            return interface["mac"]
    return None


def _txt_str(properties: dict, key: str) -> str | None:
    """Return a TXT record value as string.

    Depending on the HA version, properties are either
    dict[str, str] or dict[str, list[bytes]].
    """
    value = properties.get(key)
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    if isinstance(value, list):
        if not value:
            return None
        first = value[0]
        if isinstance(first, (bytes, bytearray)):
            return bytes(first).decode("utf-8", "replace")
        return str(first) if first is not None else None
    return str(value)


class AirlinoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirLino."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._api_version: str = DEFAULT_API_VERSION

    @override
    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except UnsupportedApiVersion:
                errors["base"] = "unsupported_api_version"
            except CannotConnect, CannotIdentify:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["mac"], raise_on_progress=False)
                for progress in self.hass.config_entries.flow.async_progress_by_handler(
                    DOMAIN
                ):
                    if (
                        progress["flow_id"] != self.flow_id
                        and progress["context"].get("unique_id") == info["mac"]
                    ):
                        self.hass.config_entries.flow.async_abort(progress["flow_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        "port": user_input.get("port", DEFAULT_PORT),
                        "api_version": info["api_version"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an AirLino device."""
        model = _txt_str(discovery_info.properties, "model")
        if model not in VALID_MODELS:
            _LOGGER.debug(
                "Ignoring discovered device at %s: unsupported model %r",
                discovery_info.host,
                model,
            )
            return self.async_abort(reason="not_airlino")
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        # The device announces its API version in the TXT record ("api=v22").
        self._api_version = (
            _txt_str(discovery_info.properties, "api") or DEFAULT_API_VERSION
        )
        _LOGGER.debug(
            "AirLino discovered via zeroconf: host=%s port=%s api_version=%s",
            self._host,
            self._port,
            self._api_version,
        )

        try:
            info = await validate_input(
                self.hass,
                {CONF_HOST: self._host, "port": self._port},
                api_version=self._api_version,
            )
        except UnsupportedApiVersion:
            _LOGGER.debug(
                "Ignoring discovered AirLino at %s:%s with unsupported API version %s",
                self._host,
                self._port,
                self._api_version,
            )
            return self.async_abort(reason="unsupported_api_version")
        except (CannotConnect, CannotIdentify) as err:
            _LOGGER.debug(
                "Could not connect to or identify discovered AirLino at %s:%s: %r",
                self._host,
                self._port,
                err,
                exc_info=err.__cause__,
            )
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception during discovery")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(info["mac"])
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": info["title"]}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the confirmation step for discovered devices."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={
                    CONF_HOST: self._host,
                    "port": self._port,
                    "api_version": self._api_version,
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.context.get("title_placeholders", {}),
        )


class UnsupportedApiVersion(Exception):
    """Raised when the device API is too old or unsupported."""


class CannotConnect(Exception):
    """Raised when the device cannot be reached."""


class CannotIdentify(Exception):
    """Raised when the device could not be identified."""
