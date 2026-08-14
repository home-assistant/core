"""Config flow for the Refoss integration."""

from ipaddress import AddressValueError, IPv4Address
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import TextSelector

from .const import DISCOVERY_TIMEOUT, DOMAIN, LOGGER
from .util import refoss_discovery_server


def _optional_ipv4_address(value: str) -> str:
    """Validate an optional IPv4 address."""
    value = value.strip()
    if not value:
        return value
    try:
        return str(IPv4Address(value))
    except AddressValueError as err:
        raise vol.Invalid("invalid IPv4 address") from err


STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Optional(CONF_HOST, default=""): TextSelector()}
)


async def _async_has_devices(hass: HomeAssistant, host: str | None = None) -> bool:
    """Return whether devices can be discovered."""
    refoss_discovery = await refoss_discovery_server(hass)
    devices = await refoss_discovery.broadcast_msg(
        wait_for=DISCOVERY_TIMEOUT, host=host
    )
    if host is not None:
        devices = [device for device in devices if device.inner_ip == host]
    LOGGER.debug(
        "Discovered devices: [%s]", ", ".join(info.dev_name for info in devices)
    )
    return bool(devices)


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
                host = _optional_ipv4_address(user_input[CONF_HOST]) or None
            except vol.Invalid:
                errors[CONF_HOST] = "invalid_ipv4_address"
            else:
                if await _async_has_devices(self.hass, host):
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data={CONF_HOST: host} if host else {},
                    )
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {CONF_HOST: reconfigure_entry.data.get(CONF_HOST, "")},
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
                host = _optional_ipv4_address(user_input[CONF_HOST]) or None
            except vol.Invalid:
                errors[CONF_HOST] = "invalid_ipv4_address"
            else:
                if await _async_has_devices(self.hass, host):
                    await self.async_set_unique_id(DOMAIN)
                    return self.async_create_entry(
                        title="Refoss", data={CONF_HOST: host} if host else {}
                    )
                if host:
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
