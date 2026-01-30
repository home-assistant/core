"""Config flow for Lunatone."""

from typing import Any, Final

import aiohttp
from lunatone_rest_api_client import Auth, Info
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

DATA_SCHEMA: Final[vol.Schema] = vol.Schema(
    {vol.Required(CONF_URL, default="http://"): cv.string},
)


def compose_title(name: str | None, serial_number: int) -> str:
    """Compose a title string from a given name and serial number."""
    return f"{name or 'DALI Gateway'} {serial_number}"


class LunatoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    _discovered_ip: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            data = {CONF_URL: url}
            self._async_abort_entries_match(data)
            auth_api = Auth(
                session=async_get_clientsession(self.hass),
                base_url=url,
            )
            info_api = Info(auth_api)
            try:
                await info_api.async_update()
            except aiohttp.InvalidUrlClientError:
                errors["base"] = "invalid_url"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if info_api.name is None or info_api.serial_number is None:
                    errors["base"] = "missing_device_info"
                else:
                    await self.async_set_unique_id(str(info_api.serial_number))
                    if self.source == SOURCE_RECONFIGURE:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            data_updates=data,
                            title=compose_title(info_api.name, info_api.serial_number),
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=compose_title(info_api.name, info_api.serial_number),
                        data={CONF_URL: url},
                    )
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {vol.Required(CONF_URL, default=entry.data[CONF_URL]): cv.string},
                ),
                errors=errors,
                description_placeholders={CONF_NAME: entry.title},
            )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by dhcp discovery."""
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured()

        self._discovered_ip = discovery_info.ip

        return self.async_show_form(step_id="dhcp_confirm")

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device."""
        if user_input is not None:
            return await self.async_step_user(
                {CONF_URL: f"http://{self._discovered_ip}"}
            )
        return self.async_show_form(
            step_id="dhcp_confirm",
            description_placeholders={CONF_IP_ADDRESS: self._discovered_ip},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_user(user_input)
