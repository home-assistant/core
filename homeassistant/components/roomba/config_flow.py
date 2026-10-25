"""Config flow to configure roomba component."""

import asyncio
from typing import Any, override

import probatio
from roombapy import (
    RoombaConnectionError,
    RoombaDiscovery,
    RoombaInfo,
    RoombaPassword,
    generate_tls_context,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import (
    CannotConnect,
    async_connect_or_timeout,
    async_create_roomba,
    async_disconnect_or_timeout,
)
from .const import CONF_BLID, DOMAIN, ROOMBA_SESSION

ROOMBA_DISCOVERY_LOCK = "roomba_discovery_lock"
ALL_ATTEMPTS = 2
HOST_ATTEMPTS = 6
ROOMBA_WAKE_TIME = 6

AUTH_HELP_URL_KEY = "auth_help_url"
AUTH_HELP_URL_VALUE = (
    "https://www.home-assistant.io/integrations/roomba/#retrieving-your-credentials"
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    roomba = await async_create_roomba(
        hass, data[CONF_HOST], data[CONF_BLID], data[CONF_PASSWORD]
    )

    info = await async_connect_or_timeout(hass, roomba)
    if info:
        await async_disconnect_or_timeout(hass, roomba)

    return {
        ROOMBA_SESSION: info[ROOMBA_SESSION],
        CONF_NAME: info[CONF_NAME],
        CONF_HOST: data[CONF_HOST],
    }


class RoombaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Roomba configuration flow."""

    VERSION = 1

    name: str | None = None
    blid: str
    host: str | None = None

    def __init__(self) -> None:
        """Initialize the roomba flow."""
        self.discovered_robots: dict[str, RoombaInfo] = {}

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        return await self._async_step_discovery(
            discovery_info.host, discovery_info.hostname.lower().removesuffix(".local.")
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        return await self._async_step_discovery(
            discovery_info.ip, discovery_info.hostname
        )

    async def _async_step_discovery(
        self, ip_address: str, hostname: str
    ) -> ConfigFlowResult:
        """Handle any discovery."""
        self._async_abort_entries_match({CONF_HOST: ip_address})

        self.host = ip_address

        # Actively probe the device at this IP for its real blid. This is
        # authoritative and handles two cases where the hostname can't be
        # trusted: some routers substitute a user-assigned friendly name
        # for the DHCP/mDNS hostname instead of irobot-<blid>/roomba-<blid>,
        # and even a well-formed hostname's blid may be truncated if the
        # hostname exceeds length limits somewhere in the chain.
        if devices := await _async_discover_roombas(self.hass, self.host):
            self.blid = devices[0].blid
        elif hostname.startswith(("irobot-", "roomba-")):
            self.blid = _async_blid_from_hostname(hostname)
        else:
            return self.async_abort(reason="not_irobot_device")

        await self.async_set_unique_id(self.blid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: ip_address})

        # Because the hostname is so long some sources may
        # truncate the hostname since it will be longer than
        # the valid allowed length. If we already have a flow
        # going for a longer hostname we abort so the user
        # does not see two flows if discovery fails.
        for progress in self._async_in_progress():
            flow_unique_id = progress["context"].get("unique_id")
            if not flow_unique_id:
                continue
            if flow_unique_id.startswith(self.blid):
                return self.async_abort(reason="short_blid")
            if self.blid.startswith(flow_unique_id):
                self.hass.config_entries.flow.async_abort(progress["flow_id"])

        self.context["title_placeholders"] = {"host": self.host, "name": self.blid}
        return await self.async_step_user()

    async def _async_start_link(self) -> ConfigFlowResult:
        """Start linking."""
        assert self.host
        device = self.discovered_robots[self.host]
        self.blid = device.blid
        self.name = device.robot_name
        await self.async_set_unique_id(self.blid, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return await self.async_step_link()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

        hosts: dict[str | None, str] = {
            **{
                device.ip: f"{device.robot_name} ({device.ip})"
                for device in devices
                if device.blid not in already_configured
            },
            None: "Manually add a Roomba or Braava",
        }

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Optional("host"): probatio.In(hosts)}
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                description_placeholders={AUTH_HELP_URL_KEY: AUTH_HELP_URL_VALUE},
                data_schema=probatio.Schema(
                    {probatio.Required(CONF_HOST, default=self.host): str}
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

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with the Roomba.

        Given a configured host, will ask the user to press the home and target buttons
        to connect to the device.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="link",
                description_placeholders={CONF_NAME: self.name or self.blid},
            )
        assert self.host
        tls_context = await self.hass.async_add_executor_job(generate_tls_context)
        roomba_pw = RoombaPassword(self.host, tls_context=tls_context)

        if not (password := await roomba_pw.get_password()):
            return await self.async_step_link_manual()

        config = {
            CONF_HOST: self.host,
            CONF_BLID: self.blid,
            CONF_PASSWORD: password,
        }

        if not self.name:
            try:
                info = await validate_input(self.hass, config)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

            self.name = info[CONF_NAME]
        assert self.name
        return self.async_create_entry(title=self.name, data=config)

    async def async_step_link_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual linking."""
        errors = {}

        if user_input is not None:
            config = {
                CONF_HOST: self.host,
                CONF_BLID: self.blid,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                info = await validate_input(self.hass, config)
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            else:
                return self.async_create_entry(title=info[CONF_NAME], data=config)

        return self.async_show_form(
            step_id="link_manual",
            description_placeholders={AUTH_HELP_URL_KEY: AUTH_HELP_URL_VALUE},
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            errors=errors,
        )


@callback
def _async_get_roomba_discovery() -> RoombaDiscovery:
    """Create a discovery object."""
    return RoombaDiscovery()


@callback
def _async_blid_from_hostname(hostname: str) -> str:
    """Extract the blid from the hostname."""
    return hostname.split("-")[1].split(".", maxsplit=1)[0].upper()


async def _async_discover_roombas(
    hass: HomeAssistant, host: str | None = None
) -> list[RoombaInfo]:
    discovered_hosts: set[str] = set()
    devices: list[RoombaInfo] = []
    discover_lock = hass.data.setdefault(ROOMBA_DISCOVERY_LOCK, asyncio.Lock())
    discover_attempts = HOST_ATTEMPTS if host else ALL_ATTEMPTS

    for attempt in range(discover_attempts + 1):
        async with discover_lock:
            discovery = _async_get_roomba_discovery()
            discovered: set[RoombaInfo] = set()
            try:
                if host:
                    device = await discovery.get(host)
                    if device:
                        discovered.add(device)
                else:
                    discovered = await discovery.get_all()
            except OSError, RoombaConnectionError:
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
                await discovery.aclose()

        if host and host in discovered_hosts:
            return devices

        await asyncio.sleep(ROOMBA_WAKE_TIME)

    return devices
