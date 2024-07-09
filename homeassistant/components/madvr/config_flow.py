"""Config flow for the integration."""

import asyncio
import logging
from typing import Any

import aiohttp
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback

from . import MadVRConfigEntry
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


async def test_connection(hass: HomeAssistant, host: str, port: int) -> str:
    """Test if we can connect to the device and grab the mac."""
    madvr_client = Madvr(host=host, port=port, loop=hass.loop)
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
    await close_test_connection(madvr_client)
    _LOGGER.debug("Connection test successful")
    return mac_address


async def close_test_connection(madvr_client: Madvr) -> None:
    """Close the test connection."""
    _LOGGER.debug("Closing test connection")
    madvr_client.stop()
    await madvr_client.async_cancel_tasks()
    await madvr_client.close_connection()


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
                mac = await test_connection(self.hass, host, port)
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: MadVRConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return MadVROptionsFlowHandler(config_entry)


class MadVROptionsFlowHandler(OptionsFlow):
    """Handle an options flow for the integration."""

    def __init__(self, config_entry: MadVRConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            new_data = {**self.config_entry.data, **user_input}
            # there could be a situation where user changes the IP to "add" a new device so we need to update mac too
            try:
                # ensure we can connect and get the mac address from device
                mac = await test_connection(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"
            else:
                if not mac:
                    errors["base"] = "no_mac"
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                # reload the entity if changed
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        # if error or initial load, show the form
        options = self.config_entry.data
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=options.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=options.get(CONF_PORT, 44077)): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
