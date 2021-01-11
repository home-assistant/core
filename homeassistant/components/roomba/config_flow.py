"""Config flow to configure roomba component."""
import asyncio
import logging

import async_timeout
from roombapy import Roomba
from roombapy.discovery import RoombaDiscovery
from roombapy.getpassword import RoombaPassword
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback

from . import CannotConnect, async_connect_or_timeout, async_disconnect_or_timeout
from .const import (
    CONF_BLID,
    CONF_CONTINUOUS,
    CONF_DELAY,
    CONF_NAME,
    DEFAULT_CONTINUOUS,
    DEFAULT_DELAY,
    ROOMBA_SESSION,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPTIONS = {CONF_CONTINUOUS: DEFAULT_CONTINUOUS, CONF_DELAY: DEFAULT_DELAY}

SOCKET_TIMEOUT = 10
DISCOVERY_TIMEOUT = 30


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    roomba = Roomba(
        address=data[CONF_HOST],
        blid=data[CONF_BLID],
        password=data[CONF_PASSWORD],
        continuous=data[CONF_CONTINUOUS],
        delay=data[CONF_DELAY],
    )

    info = await async_connect_or_timeout(hass, roomba)

    return {
        ROOMBA_SESSION: info[ROOMBA_SESSION],
        CONF_NAME: info[CONF_NAME],
        CONF_HOST: data[CONF_HOST],
    }


class RoombaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Roomba configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the roomba flow."""
        self.discovered_robots = {}
        self.name = None
        self.blid = None
        self.host = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    @callback
    def _async_get_roomba_discovery(self):
        """Create a discovery object."""
        discovery = RoombaDiscovery()
        discovery.server_socket.settimeout(SOCKET_TIMEOUT)
        return discovery

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        # Check if user chooses manual entry
        _LOGGER.warning("async_step_init user_input: %s", user_input)
        if user_input is not None and not user_input.get(CONF_HOST):
            return await self.async_step_manual()

        if (
            user_input is not None
            and self.discovered_robots is not None
            and user_input[CONF_HOST] in self.discovered_robots
        ):
            self.host = user_input[CONF_HOST]
            device = self.discovered_robots[self.host]
            self.blid = device.blid
            self.name = device.robot_name
            await self.async_set_unique_id(self.blid, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_link()

        devices = None
        discovery = self._async_get_roomba_discovery()
        # Find / discover robots
        try:
            with async_timeout.timeout(DISCOVERY_TIMEOUT):
                devices = await self.hass.async_add_executor_job(discovery.get_all)
        except asyncio.TimeoutError:
            return await self.async_step_manual()

        if devices:
            # Find already configured hosts
            already_configured = self._async_current_ids(False)
            self.discovered_robots = {
                device.ip: device
                for device in devices
                if device.blid not in already_configured
            }

        if not self.discovered_robots:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("host"): vol.In(
                        {
                            **{
                                device.ip: f"{device.robot_name} ({device.ip})"
                                for device in devices
                            },
                            None: "Manually add a Roomba or Braava",
                        }
                    )
                }
            ),
        )

    async def async_step_manual(self, user_input=None):
        """Handle manual device setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            )

        if any(
            user_input["host"] == entry.data.get("host")
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")

        self.host = user_input[CONF_HOST]
        return await self.async_step_link()

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Roomba.

        Given a configured host, will ask the user to press the home and target buttons
        to connect to the device.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        if not self.blid:
            discovery = self._async_get_roomba_discovery()
            robot = None
            try:
                with async_timeout.timeout(SOCKET_TIMEOUT):
                    robot = await self.hass.async_add_executor_job(
                        discovery.get, self.host
                    )
            except asyncio.TimeoutError:
                return self.async_abort(reason="cannot_connect")

            if not robot:
                return self.async_abort(reason="cannot_connect")
            self.blid = robot.blid
            await self.async_set_unique_id(self.blid, raise_on_progress=False)
            self._abort_if_unique_id_configured()

        getpassword = RoombaPassword(self.host)
        password = None
        try:
            with async_timeout.timeout(120):
                password = await self.hass.async_add_executor_job(
                    getpassword.get_password, self.host
                )
        except Exception:  # pylint: disable=broad-except
            return await self.async_step_link_manual()

        if not password:
            return await self.async_step_link_manual()

        return self.async_create_entry(
            title=self.name or self.host,
            data={
                CONF_HOST: self.host,
                CONF_BLID: self.blid,
                CONF_PASSWORD: password,
                **DEFAULT_OPTIONS,
            },
        )

    async def async_step_link_manual(self, user_input=None):
        """Handle manual linking."""
        errors = {}

        if user_input is not None:
            config = {
                CONF_HOST: self.host,
                CONF_BLID: self.blid,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                **DEFAULT_OPTIONS,
            }
            try:
                info = await validate_input(self.hass, config)
            except CannotConnect:
                errors = {"base": "cannot_connect"}

            if not errors:
                await async_disconnect_or_timeout(self.hass, info[ROOMBA_SESSION])
                return self.async_create_entry(title=self.host, data=config)

        return self.async_show_form(
            step_id="link_manual",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CONTINUOUS,
                        default=self.config_entry.options.get(
                            CONF_CONTINUOUS, DEFAULT_CONTINUOUS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_DELAY,
                        default=self.config_entry.options.get(
                            CONF_DELAY, DEFAULT_DELAY
                        ),
                    ): int,
                }
            ),
        )
