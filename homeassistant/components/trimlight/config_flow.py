"""Config flow for the Trimlight integration."""

from typing import Any, override

from aiotrimlight import (
    TrimlightClient,
    TrimlightCommandError,
    TrimlightConnectionError,
    TrimlightDiscoveryError,
    TrimlightHTTPError,
    TrimlightProtocolError,
    parse_discovery_properties,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_DID, DOMAIN


class TrimlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trimlight."""

    VERSION = 1

    _host: str
    _mac: str
    _name: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated flow."""
        return self.async_abort(reason="not_supported")

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        try:
            discovery = parse_discovery_properties(discovery_info.properties)
        except TrimlightDiscoveryError:
            return self.async_abort(reason="invalid_discovery_info")

        host = discovery_info.host
        mac = format_mac(discovery.mac_address)
        await self.async_set_unique_id(discovery.did)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        client = TrimlightClient(host, async_get_clientsession(self.hass))
        try:
            await client.get_device_info()
        except TrimlightConnectionError, TrimlightHTTPError:
            return self.async_abort(reason="cannot_connect")
        except TrimlightCommandError, TrimlightProtocolError:
            return self.async_abort(reason="invalid_response")

        service_name = discovery_info.name.removesuffix(f".{discovery_info.type}")
        self._host = host
        self._mac = mac
        self._name = discovery.name or service_name
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered Trimlight controller."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_HOST: self._host,
                    CONF_DID: self.unique_id,
                    CONF_MAC: self._mac,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "host": self._host,
                "name": self._name,
            },
        )
