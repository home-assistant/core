"""Config flow to configure the Arcam FMJ component."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from arcam.fmj.client import Client, ConnectionFailed
from arcam.fmj.utils import get_uniqueid_from_host, get_uniqueid_from_udn
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, DOMAIN_DATA_ENTRIES


def get_entry_client(hass: HomeAssistant, entry: ConfigEntry) -> Client:
    """Retrieve client associated with a config entry."""
    client: Client = hass.data[DOMAIN_DATA_ENTRIES][entry.entry_id]
    return client


class ArcamFmjFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    async def _async_set_unique_id_and_update(
        self, host: str, port: int, uuid: str
    ) -> None:
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured({CONF_HOST: host, CONF_PORT: port})

    async def _async_check_and_create(self, host: str, port: int) -> ConfigFlowResult:
        client = Client(host, port)
        try:
            await client.start()
        except ConnectionFailed:
            return self.async_abort(reason="cannot_connect")
        finally:
            await client.stop()

        return self.async_create_entry(
            title=f"{DEFAULT_NAME} ({host})",
            data={CONF_HOST: host, CONF_PORT: port},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uuid = await get_uniqueid_from_host(
                async_get_clientsession(self.hass), user_input[CONF_HOST]
            )
            if uuid:
                await self._async_set_unique_id_and_update(
                    user_input[CONF_HOST], user_input[CONF_PORT], uuid
                )

            return await self._async_check_and_create(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )

        fields = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        context = self.context
        placeholders = {
            "host": context[CONF_HOST],
        }
        context["title_placeholders"] = placeholders

        if user_input is not None:
            return await self._async_check_and_create(
                context[CONF_HOST], context[CONF_PORT]
            )

        return self.async_show_form(
            step_id="confirm", description_placeholders=placeholders
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered device."""
        host = str(urlparse(discovery_info.ssdp_location).hostname)
        port = DEFAULT_PORT
        uuid = get_uniqueid_from_udn(discovery_info.upnp[ssdp.ATTR_UPNP_UDN])
        if not uuid:
            return self.async_abort(reason="cannot_connect")

        await self._async_set_unique_id_and_update(host, port, uuid)

        context = self.context
        context[CONF_HOST] = host
        context[CONF_PORT] = DEFAULT_PORT
        return await self.async_step_confirm()
