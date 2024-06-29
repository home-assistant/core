"""Config flow for the integration."""

import asyncio
import logging
from typing import Any

import aiohttp
from madvr.errors import CannotConnect
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: MadVRConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return MadVROptionsFlowHandler(config_entry)

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        config = {
            CONF_NAME: import_config.get(CONF_NAME, DEFAULT_NAME),
            CONF_HOST: import_config.get(CONF_HOST, ""),
            CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
        }

        result = await self.async_step_user(config)

        if errors := result.get("errors"):
            return self.async_abort(reason=errors["base"])
        return result


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
        if user_input is not None:
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            # reload the entity if changed
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        options = self.config_entry.data
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=options.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=options.get(CONF_PORT, 44077)): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
