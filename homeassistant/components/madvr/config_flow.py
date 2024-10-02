"""Config flow for the integration."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .errors import CannotConnect

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

RETRY_INTERVAL = 1


class MadVRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 1

    entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._handle_config_step(user_input)

    async def async_step_reconfigure(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self._handle_config_step(user_input, step_id="reconfigure_confirm")

    async def _handle_config_step(
        self, user_input: dict[str, Any] | None = None, step_id: str = "user"
    ) -> ConfigFlowResult:
        """Handle the configuration step for both initial setup and reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("User input: %s", user_input)
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                mac = await test_connection(self.hass, host, port)
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"
            else:
                if not mac:
                    errors["base"] = "no_mac"
                else:
                    _LOGGER.debug("MAC address found: %s", mac)
                    # abort if the detected mac differs from the one in the entry
                    if self.entry:
                        existing_mac = self.entry.unique_id
                        if existing_mac != mac:
                            _LOGGER.debug(
                                "MAC address changed from %s to %s", existing_mac, mac
                            )
                            # abort
                            return self.async_abort(reason="set_up_new_device")

                        _LOGGER.debug("Reconfiguration done")
                        return self.async_update_reload_and_abort(
                            entry=self.entry,
                            data={**user_input, CONF_HOST: host, CONF_PORT: port},
                            reason="reconfigure_successful",
                        )
                    # abort if already configured with same mac
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                    _LOGGER.debug("Configuration successful")
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data=user_input,
                    )
        _LOGGER.debug("Showing form with errors: %s", errors)
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )


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
