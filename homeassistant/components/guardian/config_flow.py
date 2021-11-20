"""Config flow for Elexa Guardian integration."""
from __future__ import annotations

from typing import Any

from aioguardian import Client
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_UID, DOMAIN, LOGGER

DEFAULT_PORT = 7777

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

UNIQUE_ID = "guardian_{0}"


@callback
def async_get_pin_from_discovery_hostname(hostname: str) -> str:
    """Get the device's 4-digit PIN from its zeroconf-discovered hostname."""
    return hostname.split(".")[0].split("-")[1]


@callback
def async_get_pin_from_uid(uid: str) -> str:
    """Get the device's 4-digit PIN from its UID."""
    return uid[-4:]


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    async with Client(data[CONF_IP_ADDRESS]) as client:
        ping_data = await client.system.ping()

    return {
        CONF_UID: ping_data["data"]["uid"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elexa Guardian."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.discovery_info: dict[str, Any] = {}

    async def _async_set_unique_id(self, pin: str) -> None:
        """Set the config entry's unique ID (based on the device's 4-digit PIN)."""
        await self.async_set_unique_id(UNIQUE_ID.format(pin))
        if self.discovery_info:
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: self.discovery_info[CONF_IP_ADDRESS]}
            )
        else:
            self._abort_if_unique_id_configured()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle configuration via the UI."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors={}
            )

        try:
            info = await validate_input(self.hass, user_input)
        except GuardianError as err:
            LOGGER.error("Error while connecting to unit: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={CONF_IP_ADDRESS: "cannot_connect"},
            )

        pin = async_get_pin_from_uid(info[CONF_UID])
        await self._async_set_unique_id(pin)

        return self.async_create_entry(
            title=info[CONF_UID], data={CONF_UID: info["uid"], **user_input}
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle the configuration via dhcp."""
        self.discovery_info = {
            CONF_IP_ADDRESS: discovery_info[dhcp.IP_ADDRESS],
            CONF_PORT: DEFAULT_PORT,
        }
        return await self._async_handle_discovery()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle the configuration via zeroconf."""
        self.discovery_info = {
            CONF_IP_ADDRESS: discovery_info[zeroconf.ATTR_HOST],
            CONF_PORT: discovery_info[zeroconf.ATTR_PORT],
        }
        pin = async_get_pin_from_discovery_hostname(
            discovery_info[zeroconf.ATTR_HOSTNAME]
        )
        await self._async_set_unique_id(pin)
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> FlowResult:
        """Handle any discovery."""
        self.context[CONF_IP_ADDRESS] = self.discovery_info[CONF_IP_ADDRESS]
        if any(
            self.context[CONF_IP_ADDRESS] == flow["context"][CONF_IP_ADDRESS]
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish the configuration via any discovery."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(step_id="discovery_confirm")
        return await self.async_step_user(self.discovery_info)
