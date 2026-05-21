"""Config flow to configure the Arcam FMJ component."""

import socket
from typing import Any
from urllib.parse import urlparse

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import Client
from arcam.fmj.utils import get_uniqueid_from_host, get_uniqueid_from_udn
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN


class ArcamFmjFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    host: str
    port: int

    async def _async_set_unique_id_and_update(
        self, host: str, port: int, uuid: str
    ) -> None:
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured({CONF_HOST: host, CONF_PORT: port})

    async def _async_try_connect(self, host: str, port: int) -> None:
        """Verify the device is reachable."""
        client = Client(host, port)
        try:
            await client.start()
        finally:
            await client.stop()

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

            try:
                await self._async_try_connect(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except socket.gaierror:
                errors["base"] = "invalid_host"
            except TimeoutError:
                errors["base"] = "timeout_connect"
            except ConnectionRefusedError:
                errors["base"] = "connection_refused"
            except ConnectionFailed, OSError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({user_input[CONF_HOST]})",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                )

        fields = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }
        schema = vol.Schema(fields)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        placeholders = {"host": self.host}
        self.context["title_placeholders"] = placeholders

        if user_input is not None:
            return self.async_create_entry(
                title=f"{DEFAULT_NAME} ({self.host})",
                data={CONF_HOST: self.host, CONF_PORT: self.port},
            )

        return self.async_show_form(
            step_id="confirm", description_placeholders=placeholders
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered device."""
        host = str(urlparse(discovery_info.ssdp_location).hostname)
        port = DEFAULT_PORT
        uuid = get_uniqueid_from_udn(discovery_info.upnp[ATTR_UPNP_UDN])
        if not uuid:
            return self.async_abort(reason="cannot_connect")

        await self._async_set_unique_id_and_update(host, port, uuid)

        try:
            await self._async_try_connect(host, port)
        except ConnectionFailed, OSError:
            return self.async_abort(reason="cannot_connect")

        self.host = host
        self.port = port
        return await self.async_step_confirm()
