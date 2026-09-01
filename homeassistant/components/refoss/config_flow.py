"""Config flow for the Refoss integration."""

import asyncio
from ipaddress import AddressValueError, IPv4Address
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOSTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import DISCOVERY_TIMEOUT, DOMAIN, LOGGER
from .util import configured_hosts, refoss_discovery_server


def _ipv4_addresses(values: list[str]) -> list[str]:
    """Validate and normalize IPv4 addresses."""
    hosts: list[str] = []
    for value in values:
        value = value.strip()
        if not value:
            continue
        try:
            host = str(IPv4Address(value))
        except AddressValueError as err:
            raise vol.Invalid("invalid IPv4 address") from err
        if host not in hosts:
            hosts.append(host)
    return hosts


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOSTS, default=[]): TextSelector(
            TextSelectorConfig(multiple=True)
        )
    }
)


async def _async_has_devices(hass: HomeAssistant, hosts: list[str]) -> bool:
    """Return whether devices can be discovered."""
    refoss_discovery = await refoss_discovery_server(hass)
    results = await asyncio.gather(
        *(
            refoss_discovery.broadcast_msg(wait_for=DISCOVERY_TIMEOUT, host=host)
            for host in hosts or [None]
        )
    )
    devices = {device.uuid: device for result in results for device in result}.values()
    if hosts:
        devices = [device for device in devices if device.inner_ip in hosts]
    LOGGER.debug(
        "Discovered devices: [%s]", ", ".join(info.dev_name for info in devices)
    )
    if not hosts:
        return bool(devices)
    return set(hosts) <= {device.inner_ip for device in devices}


class RefossConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Refoss."""

    VERSION = 1

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of Refoss discovery."""
        reconfigure_entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                hosts = _ipv4_addresses(user_input[CONF_HOSTS])
            except vol.Invalid:
                errors[CONF_HOSTS] = "invalid_ipv4_address"
            else:
                if await _async_has_devices(self.hass, hosts):
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data={CONF_HOSTS: hosts} if hosts else {},
                    )
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {CONF_HOSTS: configured_hosts(reconfigure_entry.data)},
            ),
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                hosts = _ipv4_addresses(user_input[CONF_HOSTS])
            except vol.Invalid:
                errors[CONF_HOSTS] = "invalid_ipv4_address"
            else:
                if await _async_has_devices(self.hass, hosts):
                    await self.async_set_unique_id(DOMAIN)
                    return self.async_create_entry(
                        title="Refoss", data={CONF_HOSTS: hosts} if hosts else {}
                    )
                if hosts:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
