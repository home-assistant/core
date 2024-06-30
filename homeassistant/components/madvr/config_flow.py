"""Config flow for the integration."""

import asyncio
import logging
from typing import Any

import aiohttp
from madvr.errors import CannotConnect
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST,
        ): str,
        vol.Required(
            CONF_PORT,
            default=DEFAULT_PORT,
        ): int,
    }
)


class MadVRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # prevent multiple instances with same host
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                # get the mac address from device
                mac = await self._test_connection(host, port)
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"

            if not errors:
                # persist the mac address between HA restarts
                user_input[CONF_MAC] = mac
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )
        # Whether it's the first attempt or a retry, show the form
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def _test_connection(self, host: str, port: int) -> str:
        """Test if we can connect to the device."""
        madvr_client = Madvr(host=host, port=port)
        _LOGGER.debug("Testing connection to MadVR at %s:%s", host, port)
        # try to connect
        try:
            await asyncio.wait_for(madvr_client.open_connection(), timeout=15)
        # connection can raise HeartBeatError if the device is not available or connection does not work
        except (TimeoutError, aiohttp.ClientError, OSError, HeartBeatError) as err:
            _LOGGER.error("Error connecting to MadVR: %s", err)
            raise CannotConnect from err

        # check if we are connected
        if not madvr_client.connected():
            raise CannotConnect("Connection failed")

        # wait for client to capture device info
        await asyncio.sleep(2)
        # get mac from device
        mac_address = madvr_client.mac_address
        if not mac_address:
            # its not critical because it should get picked up by the client eventually but not ideal
            _LOGGER.error("No MAC address found")
        else:
            _LOGGER.debug("Connected to MadVR with MAC: %s", mac_address)
        # close this connection because this client object will not be reused
        madvr_client.stop()
        await madvr_client.close_connection()

        _LOGGER.debug("Connection test successful")
        return mac_address
