"""Config flow for the integration."""

import asyncio
import logging
from typing import Any

import aiohttp
from madvr.errors import CannotConnect
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .coordinator import MadVRCoordinator

type MadVRConfigEntry = ConfigEntry[MadVRCoordinator]


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            try:
                await self._test_connection(host, port)
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"
        # Whether it's the first attempt or a retry, show the form
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def _test_connection(self, host: str, port: int):
        """Test if we can connect to the device."""
        try:
            madvr_client = Madvr(host=host, port=port)
            _LOGGER.debug("Testing connection to MadVR at %s:%s", host, port)
            # turn on the device
            await madvr_client.power_on()
        except ValueError as err:
            _LOGGER.error("Error sending magic packet: %s", err)
            raise CannotConnect from err
        # wait for it to be available (envy takes about 15s to boot)
        await asyncio.sleep(15)
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

        _LOGGER.debug("Connection test successful")
