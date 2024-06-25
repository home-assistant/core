"""Config flow for the integration."""

import asyncio
import logging

import aiohttp
from madvr.madvr import HeartBeatError, Madvr
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import DOMAIN
from .coordinator import MadVRCoordinator
from .utils import CannotConnect, cancel_tasks
from .wakeonlan import send_magic_packet

_LOGGER = logging.getLogger(__name__)


class MadVRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            port = user_input.get("port", 44077)
            mac = user_input["mac"]
            keep_power_on = user_input["keep_power_on"]
            try:
                await self._test_connection(host, port, mac, keep_power_on)
                return self.async_create_entry(
                    title=user_input["name"], data=user_input
                )
            except CannotConnect:
                _LOGGER.error("CannotConnect error caught")
                errors["base"] = "cannot_connect"
                self.context["user_input"] = user_input
                # allow user to skip connection test
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("host"): str,
                    vol.Required("mac"): str,
                    vol.Optional("port", default=44077): int,
                    vol.Optional("keep_power_on", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def _test_connection(self, host, port, mac, keep_power_on: bool):
        """Test if we can connect to the device."""
        try:
            madvr_client = Madvr(host=host, port=port)
            _LOGGER.debug(
                "Testing connection to MadVR at %s:%s with mac %s", host, port, mac
            )
            # turn on the device
            send_magic_packet(mac)
            # wait for it to be available (envy takes about 15s to boot)
            await asyncio.sleep(15)
            # try to connect
            await asyncio.wait_for(madvr_client.open_connection(), timeout=15)

            # don't need tasks running
            await asyncio.sleep(2)  # let them run once
            await cancel_tasks(madvr_client)

            # check if we are connected
            if not madvr_client.connected():
                raise CannotConnect("Connection failed")

            _LOGGER.debug("Connection test successful")
            if not keep_power_on:
                _LOGGER.debug("Turning off device")
                await madvr_client.power_off()
            else:
                # remote will open a new connection, so close this one
                _LOGGER.debug("Closing connection")
                await madvr_client.close_connection()
            _LOGGER.debug("Finished testing connection")

        except ValueError as err:
            _LOGGER.error("Error sending magic packet: %s", err)
            raise CannotConnect from err
        # connection can raise HeartBeatError if the device is not available or connection does not work
        except (TimeoutError, aiohttp.ClientError, OSError, HeartBeatError) as err:
            _LOGGER.error("Error connecting to MadVR: %s", err)
            raise CannotConnect from err

    async def async_step_confirm(self, user_input=None) -> ConfigFlowResult:
        """Handle confirmation step if connection test fails."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context["user_input"]["name"],
                data=self.context["user_input"],
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self.context["user_input"]["name"]},
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return MadVROptionsFlowHandler(config_entry)


class MadVROptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for the integration."""

    def __init__(self, config_entry: ConfigEntry[MadVRCoordinator]) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            # reload the entity if changed
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.data
        data_schema = vol.Schema(
            {
                vol.Optional("name", default=options.get("name", "")): str,
                vol.Optional("host", default=options.get("host", "")): str,
                vol.Optional("mac", default=options.get("mac", "")): str,
                vol.Optional("port", default=options.get("port", 44077)): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
