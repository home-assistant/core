"""Config flow for Cambridge Audio."""

import asyncio
from typing import Any

from aiostreammagic import StreamMagicClient
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONNECT_TIMEOUT, DOMAIN, STREAM_MAGIC_EXCEPTIONS

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class CambridgeAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Cambridge Audio configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host

        await self.async_set_unique_id(discovery_info.properties["serial"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        client = StreamMagicClient(host, async_get_clientsession(self.hass))
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT):
                await client.connect()
        except STREAM_MAGIC_EXCEPTIONS:
            return self.async_abort(reason="cannot_connect")

        self.data[CONF_NAME] = client.info.name

        self.context["title_placeholders"] = {
            "name": self.data[CONF_NAME],
        }
        await client.disconnect()
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data[CONF_NAME],
                data={CONF_HOST: self.data[CONF_HOST]},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self.data[CONF_NAME],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        if not user_input:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=DATA_SCHEMA,
            )
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            client = StreamMagicClient(
                user_input[CONF_HOST], async_get_clientsession(self.hass)
            )
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    await client.connect()
            except STREAM_MAGIC_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    client.info.unit_id, raise_on_progress=False
                )
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={CONF_HOST: user_input[CONF_HOST]},
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=client.info.name,
                    data={CONF_HOST: user_input[CONF_HOST]},
                )
            finally:
                await client.disconnect()
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
