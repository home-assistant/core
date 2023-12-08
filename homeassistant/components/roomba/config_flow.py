"""Config flow to configure roomba component."""
from __future__ import annotations

import asyncio
from functools import partial

from roombapy import RoombaFactory
from roombapy.discovery import RoombaDiscovery
from roombapy.getpassword import RoombaPassword
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components import dhcp, zeroconf
from homeassistant.const import CONF_DELAY, CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import CannotConnect, async_connect_or_timeout, async_disconnect_or_timeout
from .const import (
    CONF_BLID,
    CONF_CONTINUOUS,
    DEFAULT_CONTINUOUS,
    DEFAULT_DELAY,
    DOMAIN,
    ROOMBA_SESSION,
)

ROOMBA_DISCOVERY_LOCK = "roomba_discovery_lock"
ALL_ATTEMPTS = 2
HOST_ATTEMPTS = 6
ROOMBA_WAKE_TIME = 6

DEFAULT_OPTIONS = {CONF_CONTINUOUS: DEFAULT_CONTINUOUS, CONF_DELAY: DEFAULT_DELAY}

MAX_NUM_DEVICES_TO_DISCOVER = 25

AUTH_HELP_URL_KEY = "auth_help_url"
AUTH_HELP_URL_VALUE = "https://www.home-assistant.io/integrations/roomba/#manually-retrieving-your-credentials"


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    roomba = await hass.async_add_executor_job(
        partial(
            RoombaFactory.create_roomba,
            address=data[CONF_HOST],
            blid=data[CONF_BLID],
            password=data[CONF_PASSWORD],
            continuous=False,
            delay=data[CONF_DELAY],
        )
    )

    info = await async_connect_or_timeout(hass, roomba)
    if info:
        await async_disconnect_or_timeout(hass, roomba)

    return {
        ROOMBA_SESSION: info[ROOMBA_SESSION],
        CONF_NAME: info[CONF_NAME],
        CONF_HOST: data[CONF_HOST],
    }


class RoombaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Roomba configuration flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the roomba flow."""
        self.discovered_robots = {}
        self.name = None
        self.blid = None
        self.host = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        return await self._async_step_discovery(
            discovery_info.host, discovery_info.hostname.lower().rstrip(".local.")
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle dhcp discovery."""
        return await self._async_step_discovery(
            discovery_info.ip, discovery_info.hostname
        )

    async def _async_step_discovery(self, ip_address: str, hostname: str) -> FlowResult:
        """Handle any discovery."""
        self._async_abort_entries_match({CONF_HOST: ip_address})

        if not hostname.startswith(("irobot-", "roomba-")):
            return self.async_abort(reason="not_irobot_device")

        self.host = ip_address
        self.blid = _async_blid_from_hostname(hostname)
        await self.async_set_unique_id(self.blid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: ip_address})

        # Because the hostname is so long some sources may
        # truncate the hostname since it will be longer than
        # the valid allowed length. If we already have a flow
        # going for a longer hostname we abort so the user
        # does not see two flows if discovery fails.
        for progress in self._async_in_progress():
            flow_unique_id: str = progress["context"]["unique_id"]
            if flow_unique_id.startswith(self.blid):
                return self.async_abort(reason="short_blid")
            if self.blid.startswith(flow_unique_id):
                self.hass.config_entries.flow.async_abort(progress["flow_id"])

        self.context["title_placeholders"] = {"host": self.host, "name": self.blid}
        return await self.async_step_user()

    async def _async_start_link(self):
        """Start linking."""
        device = self.discovered_robots[self.host]
        self.blid = device.blid
        self.name = device.robot_name
        await self.async_set_unique_id(self.blid, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return await self.async_step_link()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        # Check if user chooses manual entry
        if user_input is not None and not user_input.get(CONF_HOST):
            return await self.async_step_manual()

        if (
            user_input is not None
            and self.discovered_robots is not None
            and user_input[CONF_HOST] in self.discovered_robots
        ):
            self.host = user_input[CONF_HOST]
            return await self._async_start_link()

        already_configured = self._async_current_ids(False)

        devices = await _async_discover_roombas(self.hass, self.host)

        if devices:
            # Find already configured hosts
            self.discovered_robots = {
                device.ip: device
                for device in devices
                if device.blid not in already_configured
            }

        if self.host and self.host in self.discovered_robots:
            # From discovery
            self.context["title_placeholders"] = {
                "host": self.host,
                "name": self.discovered_robots[self.host].robot_name,
            }
            return await self._async_start_link()

        if not self.discovered_robots:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("host"): vol.In(
                        {
                            **{
                                device.ip: f"{device.robot_name} ({device.ip})"
                                for device in devices
                                if device.blid not in already_configured
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
                description_placeholders={AUTH_HELP_URL_KEY: AUTH_HELP_URL_VALUE},
                data_schema=vol.Schema(
                    {vol.Required(CONF_HOST, default=self.host): str}
                ),
            )

        self._async_abort_entries_match({CONF_HOST: user_input["host"]})

        self.host = user_input[CONF_HOST]

        devices = await _async_discover_roombas(self.hass, self.host)
        if not devices:
            return self.async_abort(reason="cannot_connect")
        self.blid = devices[0].blid
        self.name = devices[0].robot_name

        await self.async_set_unique_id(self.blid, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return await self.async_step_link()

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Roomba.

        Given a configured host, will ask the user to press the home and target buttons
        to connect to the device.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="link",
                description_placeholders={CONF_NAME: self.name or self.blid},
            )

        roomba_pw = RoombaPassword(self.host)

        try:
            password = await self.hass.async_add_executor_job(roomba_pw.get_password)
        except OSError:
            return await self.async_step_link_manual()

        if not password:
            return await self.async_step_link_manual()

        config = {
            CONF_HOST: self.host,
            CONF_BLID: self.blid,
            CONF_PASSWORD: password,
            **DEFAULT_OPTIONS,
        }

        if not self.name:
            try:
                info = await validate_input(self.hass, config)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

            self.name = info[CONF_NAME]

        return self.async_create_entry(title=self.name, data=config)

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
                return self.async_create_entry(title=info[CONF_NAME], data=config)

        return self.async_show_form(
            step_id="link_manual",
            description_placeholders={AUTH_HELP_URL_KEY: AUTH_HELP_URL_VALUE},
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
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


@callback
def _async_get_roomba_discovery():
    """Create a discovery object."""
    discovery = RoombaDiscovery()
    discovery.amount_of_broadcasted_messages = MAX_NUM_DEVICES_TO_DISCOVER
    return discovery


@callback
def _async_blid_from_hostname(hostname):
    """Extract the blid from the hostname."""
    return hostname.split("-")[1].split(".")[0].upper()


async def _async_discover_roombas(hass, host):
    discovered_hosts = set()
    devices = []
    discover_lock = hass.data.setdefault(ROOMBA_DISCOVERY_LOCK, asyncio.Lock())
    discover_attempts = HOST_ATTEMPTS if host else ALL_ATTEMPTS

    for attempt in range(discover_attempts + 1):
        async with discover_lock:
            discovery = _async_get_roomba_discovery()
            try:
                if host:
                    device = await hass.async_add_executor_job(discovery.get, host)
                    discovered = [device] if device else []
                else:
                    discovered = await hass.async_add_executor_job(discovery.get_all)
            except OSError:
                # Socket temporarily unavailable
                await asyncio.sleep(ROOMBA_WAKE_TIME * attempt)
                continue
            else:
                for device in discovered:
                    if device.ip in discovered_hosts:
                        continue
                    discovered_hosts.add(device.ip)
                    devices.append(device)
            finally:
                discovery.server_socket.close()

        if host and host in discovered_hosts:
            return devices

        await asyncio.sleep(ROOMBA_WAKE_TIME)

    return devices
