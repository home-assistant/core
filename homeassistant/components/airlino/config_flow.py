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
from .const import DEFAULT_API_VERSION, DEFAULT_PORT, DOMAIN, VALID_MODELS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = Schema(
    {
        "host": str,
        Optional("port", default=DEFAULT_PORT): int,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict, api_version: str = DEFAULT_API_VERSION
) -> dict:
    """Validate the user input allows us to connect."""
    api = AirlinoApi(
        host=data[CONF_HOST],
        port=data.get("port", DEFAULT_PORT),
        api_version=api_version,
        session=async_get_clientsession(hass),
    )
    try:
        device_info = await api.async_get_device_info()
        network_info = await api.async_get_network_info()
    except (
        AirlinoApiConnectionError,
        AirlinoApiError,
        aiohttp.ClientError,
    ) as err:
        raise CannotConnect from err

    # The MAC address is the stable device identifier (DHCP-safe).
    # Hardware strings look like "LTH-6510CC-02DAA9A6" (MAC suffix).
    mac = _get_mac(network_info) or device_info.get("hardware")
    if not mac:
        raise CannotIdentify

    return {
        "title": device_info.get("devicename", "AirLino"),
        "mac": mac,
        "api_version": api_version,
    }


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
            except CannotConnect, CannotIdentify:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Don't fail on a pending discovery flow for the same device:
                # the user explicitly wants to add it now, so stale flows are
                # aborted first.
                await self.async_set_unique_id(info["mac"], raise_on_progress=False)
                for (
                    prog_flow
                ) in self.hass.config_entries.flow.async_progress_by_handler(DOMAIN):
                    if (
                        prog_flow["flow_id"] != self.flow_id
                        and prog_flow["context"].get("unique_id") == info["mac"]
                    ):
                        self.hass.config_entries.flow.async_abort(prog_flow["flow_id"])
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        "port": user_input["port"],
                        "api_version": info["api_version"],
                    },
                    reload_on_update=True,
                )
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        "port": user_input["port"],
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
            "AirLino discovered via zeroconf: host=%s port=%s api_version=%s "
            "properties=%s",
            self._host,
            self._port,
            self._api_version,
            discovery_info.properties,
        )

        try:
            info = await validate_input(
                self.hass,
                {CONF_HOST: self._host, "port": self._port},
                api_version=self._api_version,
            )
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
        # Existing entry with a new IP: update host/port instead of
        # creating a duplicate entry.
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                "port": self._port,
                # Keep the stored API version in sync with the device's
                # announcement (e.g. after a firmware update).
                "api_version": self._api_version,
            },
            reload_on_update=True,
        )

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


class CannotConnect(Exception):
    """Raised when the device cannot be reached."""


class CannotIdentify(Exception):
    """Raised when the device could not be identified."""
