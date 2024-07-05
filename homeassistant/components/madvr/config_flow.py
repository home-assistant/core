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

            try:
                # get the mac address from device
                mac = await self._test_connection(host, port)
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"
                mac = ""

            if not mac:
                _LOGGER.error("No MAC address found")
                if errors.get("base") != "cannot_connect":
                    errors["base"] = "no_mac"
            else:
                _LOGGER.debug("MAC address found: %s", mac)
                # this will prevent the user from adding the same device twice
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

            if not errors:
                _LOGGER.debug("Creating entry")
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
        """Test if we can connect to the device and grab the mac."""
        madvr_client = Madvr(host=host, port=port, loop=self.hass.loop)
        _LOGGER.debug("Testing connection to MadVR at %s:%s", host, port)
        # try to connect
        try:
            await asyncio.wait_for(madvr_client.open_connection(), timeout=15)
        # connection can raise HeartBeatError if the device is not available or connection does not work
        except (TimeoutError, aiohttp.ClientError, OSError, HeartBeatError) as err:
            _LOGGER.error("Error connecting to MadVR: %s", err)
            raise CannotConnect from err

        # check if we are connected
        if not madvr_client.connected:
            raise CannotConnect("Connection failed")

        # background tasks needed to capture realtime info
        await madvr_client.async_add_tasks()

        # wait for client to capture device info
        retry_time = 15
        while not madvr_client.mac_address and retry_time > 0:
            await asyncio.sleep(1)
            retry_time -= 1

        mac_address = madvr_client.mac_address
        if mac_address:
            _LOGGER.debug("Connected to MadVR with MAC: %s", mac_address)
        # close this connection because this client object will not be reused
        await self._close_test_connection(madvr_client)
        _LOGGER.debug("Connection test successful")
        return mac_address

    async def _close_test_connection(self, madvr_client: Madvr) -> None:
        """Close the test connection."""
        if madvr_client:
            madvr_client.stop()
            await madvr_client.async_cancel_tasks()
            await madvr_client.close_connection()
