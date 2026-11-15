"""Config flow for the AirLino integration."""

import logging
from typing import Any, TypedDict, override

from airlino_api import (
    DEFAULT_API_VERSION,
    DEFAULT_PORT,
    AirlinoApi,
    AirlinoApiConnectionError,
    AirlinoApiError,
)
from awesomeversion import AwesomeVersion
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, MIN_API_VERSION

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)


class DeviceDetails(TypedDict):
    """Details of a validated AirLino device."""

    title: str
    mac: str
    api_version: str


def _is_supported_api_version(api_version: str) -> bool:
    """Return whether the API version is supported by the integration."""
    version = AwesomeVersion(api_version)
    return version.valid and version >= MIN_API_VERSION


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], api_version: str | None = None
) -> DeviceDetails:
    """Validate the user input allows us to connect."""
    if api_version is None:
        latest = int(DEFAULT_API_VERSION.removeprefix("v"))
        minimum = int(MIN_API_VERSION.removeprefix("v"))
        versions = [f"v{version}" for version in range(latest, minimum - 1, -1)]
    elif _is_supported_api_version(api_version):
        versions = [api_version]
    else:
        raise UnsupportedApiVersion

    session = async_get_clientsession(hass)
    for version in versions:
        api = AirlinoApi(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
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
        except AirlinoApiConnectionError as err:
            raise CannotConnect from err

        # Only the interface of the active connection is reported.
        interface = network_info.get("eth") or network_info["wlan"]
        return DeviceDetails(
            title=device_info.get("devicename", "AirLino"),
            mac=format_mac(interface["mac"]),
            api_version=version,
        )

    raise UnsupportedApiVersion


class AirlinoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirLino."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._api_version: str = DEFAULT_API_VERSION

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except UnsupportedApiVersion:
                errors["base"] = "unsupported_api_version"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_API_VERSION: info["api_version"],
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
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        announced_api_version = discovery_info.properties.get("api")
        self._api_version = announced_api_version or DEFAULT_API_VERSION
        _LOGGER.debug(
            "AirLino discovered via zeroconf: host=%s port=%s api_version=%s",
            self._host,
            self._port,
            self._api_version,
        )

        try:
            info = await validate_input(
                self.hass,
                {CONF_HOST: self._host, CONF_PORT: self._port},
                api_version=announced_api_version,
            )
        except UnsupportedApiVersion:
            _LOGGER.debug(
                "Ignoring discovered AirLino at %s:%s with unsupported API version %s",
                self._host,
                self._port,
                self._api_version,
            )
            return self.async_abort(reason="unsupported_api_version")
        except CannotConnect as err:
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

        self._api_version = info["api_version"]
        await self.async_set_unique_id(info["mac"])
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_API_VERSION: self._api_version,
            }
        )

        self.context["title_placeholders"] = {"name": info["title"]}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the confirmation step for discovered devices."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_API_VERSION: self._api_version,
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
