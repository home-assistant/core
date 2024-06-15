"""Config flow for the integration."""

import asyncio

import aiohttp
from madvr.madvr import Madvr
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN


class MadVRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        # ensure device can connect
        if user_input is not None:
            host = user_input["host"]
            port = user_input.get("port", 44077)
            try:
                await self._test_connection(host, port)
                return self.async_create_entry(
                    title=user_input["name"], data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("host"): str,
                    vol.Required("mac"): str,
                    vol.Optional("port", default=44077): int,
                }
            ),
            errors=errors,
        )

    async def _test_connection(self, host, port):
        """Test if we can connect to the device."""
        try:
            madvr_client = Madvr(host=host, port=port)
            await asyncio.wait_for(madvr_client.open_connection(), timeout=5)
            madvr_client.stop()
            await madvr_client.close_connection()
            # dont want it pinging until added
            if madvr_client.ping_task:
                madvr_client.ping_task.cancel()
        except (TimeoutError, aiohttp.ClientError, OSError) as err:
            raise CannotConnect from err


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
