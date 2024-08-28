"""Config flow for HLK-SW16."""

import asyncio
from typing import Any

from hlk_sw16 import create_hlk_sw16_connection
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
)
from .errors import CannotConnect

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)


async def connect_client(hass, user_input):
    """Connect the HLK-SW16 client."""
    client_aw = create_hlk_sw16_connection(
        host=user_input[CONF_HOST],
        port=user_input[CONF_PORT],
        loop=hass.loop,
        timeout=CONNECTION_TIMEOUT,
        reconnect_interval=DEFAULT_RECONNECT_INTERVAL,
        keep_alive_interval=DEFAULT_KEEP_ALIVE_INTERVAL,
    )
    async with asyncio.timeout(CONNECTION_TIMEOUT):
        return await client_aw


async def validate_input(hass: HomeAssistant, user_input):
    """Validate the user input allows us to connect."""
    try:
        client = await connect_client(hass, user_input)
    except TimeoutError as err:
        raise CannotConnect from err

    try:

        def disconnect_callback():
            if client.in_transaction:
                client.active_transaction.set_exception(CannotConnect)

        client.disconnect_callback = disconnect_callback
        await client.status()
    except CannotConnect:
        client.disconnect_callback = None
        client.stop()
        raise

    client.disconnect_callback = None
    client.stop()


class SW16FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a HLK-SW16 config flow."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                await validate_input(self.hass, user_input)
                address = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                return self.async_create_entry(title=address, data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
