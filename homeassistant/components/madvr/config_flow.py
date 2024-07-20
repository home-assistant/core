"""Config flow for the integration."""

import asyncio
import logging
from typing import Any

import aiohttp
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .errors import CannotConnect

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

RETRY_INTERVAL = 1


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

            try:
                # ensure we can connect and get the mac address from device
                mac = await self._test_connection(host, port)
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"
            else:
                if not mac:
                    errors["base"] = "no_mac"
            if not errors:
                _LOGGER.debug("MAC address found: %s", mac)
                # this will prevent the user from adding the same device twice and persist the mac address
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                # create the entry
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        # this will show the form or allow the user to retry if there was an error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def _test_connection(self, host: str, port: int) -> str:
        """Test if we can connect to the device and grab the mac."""
        madvr_client = Madvr(host=host, port=port, loop=self.hass.loop)
        _LOGGER.debug("Testing connection to madVR at %s:%s", host, port)
        # try to connect
        try:
            await asyncio.wait_for(madvr_client.open_connection(), timeout=15)
        # connection can raise HeartBeatError if the device is not available or connection does not work
        except (TimeoutError, aiohttp.ClientError, OSError, HeartBeatError) as err:
            _LOGGER.error("Error connecting to madVR: %s", err)
            raise CannotConnect from err

        # check if we are connected
        if not madvr_client.connected:
            raise CannotConnect("Connection failed")

        # background tasks needed to capture realtime info
        await madvr_client.async_add_tasks()

        # wait for client to capture device info
        retry_time = 15
        while not madvr_client.mac_address and retry_time > 0:
            await asyncio.sleep(RETRY_INTERVAL)
            retry_time -= 1

        mac_address = madvr_client.mac_address
        if mac_address:
            _LOGGER.debug("Connected to madVR with MAC: %s", mac_address)
        # close this connection because this client object will not be reused
        await self._close_test_connection(madvr_client)
        _LOGGER.debug("Connection test successful")
        return mac_address

    async def _close_test_connection(self, madvr_client: Madvr) -> None:
        """Close the test connection."""
        madvr_client.stop()
        await madvr_client.async_cancel_tasks()
        await madvr_client.close_connection()
