"""Config flow for Vemmio."""

from typing import Any

from vemmio_client import Client, DeviceInfo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REVISION, DEFAULT_PORT, DOMAIN, LOGGER
from .exceptions import DeviceConnectionError


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vemmio."""

    VERSION = 1

    info: DeviceInfo
    host: str
    port: int

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        name = discovery_info.name
        hostname = discovery_info.hostname
        host = discovery_info.host
        port: int = discovery_info.port or DEFAULT_PORT

        LOGGER.info(
            "ZEROCONF, name: %s, hostname: %s, host: %s, port: %s",
            name,
            hostname,
            host,
            port,
        )

        try:
            self.info = await get_info(self.hass, host, port)
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        LOGGER.debug(
            "mac: %s, type: %s, revision: %s",
            self.info.mac,
            self.info.type,
            self.info.revision,
        )

        self.host = host
        if port:
            self.port = port

        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name.split(".")[0]},
                "configuration_url": f"http://{discovery_info.host}",
            }
        )

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""

        if user_input is not None:
            mac: str = dr.format_mac(self.info.mac)
            typ: str = self.info.type
            rev: str = self.info.revision
            title = f"{typ.title()} {mac}"

            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                    CONF_MAC: mac,
                    CONF_TYPE: typ,
                    CONF_REVISION: rev,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "type": self.info.type.title(),
                "host": self.host,
            },
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        if user_input is not None:
            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]

            try:
                info = await get_info(self.hass, host, port)
            except DeviceConnectionError:
                return self.async_abort(reason="reauth_unsuccessful")

            LOGGER.debug(
                "mac: %s, type: %s, revision: %s", info.mac, info.type, info.revision
            )

            mac: str = dr.format_mac(info.mac)
            typ: str = info.type
            rev: str = info.revision
            title = f"{typ.title()} {mac}"

            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(
                {
                    CONF_HOST: host,
                    CONF_PORT: port,
                }
            )

            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_MAC: mac,
                    CONF_TYPE: typ,
                    CONF_REVISION: rev,
                },
            )

        schema = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(schema))


async def get_info(hass: HomeAssistant, host: str, port: int) -> DeviceInfo:
    """Get device info."""
    session = async_get_clientsession(hass)
    client = Client(host, port, session)
    return await client.get_info()
