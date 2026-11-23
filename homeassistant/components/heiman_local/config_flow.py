"""Configure a Heiman Local Wi-Fi switch."""

from ipaddress import IPv4Address
from typing import Any, override

from heiman_local_client import (
    HeimanError,
    HeimanSwitchClient,
    SwitchInfo,
    UnsupportedDevice,
)
from probatio import Optional, Port, Required, Schema

from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_SCHEMA = Schema({Required(CONF_HOST): str, Optional(CONF_PORT, default=80): Port()})


class HeimanLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a switch manually or through zeroconf."""

    _discovered_name: str
    _discovered_data: dict[str, str | int]

    async def _async_get_switch_info(self, host: str, port: int) -> SwitchInfo:
        """Read the identity and verify that the switch reports its state."""
        client = HeimanSwitchClient(async_get_clientsession(self.hass), host, port)
        info = await client.get_info()
        await client.get_power(info)
        return info

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the connection before creating the config entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = str(IPv4Address(user_input[CONF_HOST].strip()))
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                port = user_input[CONF_PORT]
                try:
                    info = await self._async_get_switch_info(host, port)
                except UnsupportedDevice:
                    errors["base"] = "unsupported_device"
                except HeimanError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(info.mac)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info.name, data={CONF_HOST: host, CONF_PORT: port}
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_SCHEMA, user_input),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Validate the switch advertised on the local network."""
        address = discovery_info.ip_address
        if not isinstance(address, IPv4Address):
            ipv4_address = next(
                (
                    candidate
                    for candidate in discovery_info.ip_addresses
                    if isinstance(candidate, IPv4Address)
                ),
                None,
            )
            if ipv4_address is None:
                return self.async_abort(reason="no_ipv4_address")
            address = ipv4_address

        if not (port := discovery_info.port):
            return self.async_abort(reason="cannot_connect")

        host = str(address)
        try:
            info = await self._async_get_switch_info(host, port)
        except UnsupportedDevice:
            return self.async_abort(reason="unsupported_device")
        except HeimanError:
            return self.async_abort(reason="cannot_connect")

        entry = await self.async_set_unique_id(info.mac)
        if entry and entry.source == SOURCE_IGNORE:
            return self.async_abort(reason="already_configured")

        data: dict[str, str | int] = {CONF_HOST: host, CONF_PORT: port}
        self._abort_if_unique_id_configured(updates=data)
        self._discovered_name = info.name
        self._discovered_data = data
        self.context["title_placeholders"] = {"name": info.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered switch before adding it."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name, data=self._discovered_data
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._discovered_name},
        )
