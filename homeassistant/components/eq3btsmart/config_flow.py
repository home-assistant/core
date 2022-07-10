"""Config flow to configure eq3 component."""
from __future__ import annotations

import logging

import eq3bt as eq3  # pylint: disable=import-error
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EQ3Config:
    """Device Configuration."""

    def __init__(self, mac):
        """Initialize Configuration."""
        self.mac = mac


class EQ3ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EQ3 configuration flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self.conf: EQ3Config | None = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_MAC): str}),
            )

        mac = user_input[CONF_MAC]
        try:
            thermostat = eq3.Thermostat(mac)
            # TODO is this the correct way to execute synchronous calls in a config flow?
            await self.hass.async_add_executor_job(thermostat.update)
        except Exception as ex:
            _LOGGER.debug("Connection failed: %s", ex)
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_MAC, default=user_input.get(CONF_MAC, "")
                        ): str,
                    }
                ),
                errors={"base": "cannot_connect"},
            )

        self.conf = EQ3Config(mac)

        return await self.async_step_init(user_input)

    async def async_step_bluetooth(self, info):
        """Handle bluetooth discovery."""

        # TODO: would it be better to use the service_uuids instead of the name for matching?
        # BluetoothServiceInfo(name='CC-RT-BLE', address='00:1A:22:xx:xx:xx', rssi=-64,
        # manufacturer_data={0: b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'}, service_data={},
        # service_uuids=['3e135142-654f-9090-134a-a6ff5bb77046'])

        _LOGGER.debug("Discovered eQ3 thermostat using bluetooth: %s", info)
        self.conf = EQ3Config(info.address)

        return await self.async_step_init()

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        self._async_abort_entries_match({CONF_MAC: self.conf.mac})

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={
                    CONF_MAC: self.conf.mac,
                },
            )

        await self.async_set_unique_id(format_mac(self.conf.mac))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.conf.mac,
            data={CONF_MAC: self.conf.mac},
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        # TODO: what's the proper way to convert from platform-based?
        # Currently, EQ3Config contains only information about a single device
        # but the platform configuration has a list of all configured devices.
        _LOGGER.info("Got config: %s", user_input)

        mac = user_input[CONF_MAC]
        # TODO: is it worth trying to keep backwards compatibility with names?
        # name = user_input[CONF_NAME]
        thermostat = eq3.Thermostat(mac)

        # TODO: is this the correct way to execute synchronous calls in a config flow?
        # TODO: should we simply import the configuration always and let the retry process handle PlatforNotReady?
        await self.hass.async_add_executor_job(thermostat.update)

        self.conf = EQ3Config(mac)

        return await self.async_step_init(user_input)
