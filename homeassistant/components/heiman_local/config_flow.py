"""Configure a Heiman Local Wi-Fi switch."""

from ipaddress import IPv4Address
from typing import Any, override

from heiman_local_client import HeimanError, HeimanSwitchClient, UnsupportedDevice
from probatio import Optional, Port, Required, Schema

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_SCHEMA = Schema({Required(CONF_HOST): str, Optional(CONF_PORT, default=80): Port()})


class HeimanLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a switch by its local IPv4 address."""

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
                client = HeimanSwitchClient(
                    async_get_clientsession(self.hass), host, port
                )
                try:
                    info = await client.get_info()
                    await client.get_power(info)
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
