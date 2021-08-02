"""Config flow for Legrand RFLC integration."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Final

import lc7001.aio
import voluptuous

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN

_LOGGER: Final = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ConfigFlow for Legrand RFLC integration."""

    VERSION = 1

    HOST: Final = lc7001.aio.Connector.HOST

    ABORT_NO_DEVICES_FOUND: Final = "no_devices_found"
    ABORT_REAUTH_SUCCESSFUL: Final = "reauth_successful"

    ERROR_INVALID_HOST: Final = "invalid_host"
    ERROR_INVALID_AUTH: Final = "invalid_auth"

    # Automatic ssdp discovery does not help.

    # Automatic zeroconf discovery does not help.
    # Even though the device supports mDNS, it does not publish any services to discover.

    # Automatic dhcp discovery can detect conversations (udp port bootpc or bootps)
    # with network devices that present their hostname as 'Legrand LC7001'
    # with a manifest.json entry of
    #   "dhcp": [{"hostname": "legrand lc7001"}]
    # This will happen each time a Legrand LC7001 controller (re)boots.
    # Linux requires the hass process have an effective cap_net_raw capability (or be run as root)
    # for this to work.
    async def async_step_dhcp(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by dhcp discovery."""
        # example discovery_info
        # {'ip': '192.168.0.1', 'hostname': 'legrand lc7001', 'macaddress': '0026ec000000'}
        try:
            resolutions = await asyncio.get_event_loop().getaddrinfo(self.HOST, None)
        except OSError as error:
            _LOGGER.warning("OS getaddrinfo %s error %s", self.HOST, error)
            return self.async_abort(reason=self.ABORT_NO_DEVICES_FOUND)
        address = discovery_info[IP_ADDRESS]
        if any(
            resolution[4][0] == address
            for resolution in resolutions
            if resolution[0] == socket.AF_INET
        ):
            await self._async_handle_discovery_without_unique_id()
            # wait for user interaction in the next step
            return await self.async_step_user()
        _LOGGER.warning("%s does not resolve to discovered %s", self.HOST, address)
        return self.async_abort(reason=self.ABORT_NO_DEVICES_FOUND)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        host = self.HOST
        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)  # already_in_progress?
            self._abort_if_unique_id_configured()  # already_configured?
            key = None
            kwargs = {"key": key, "loop_timeout": -1}
            if CONF_PASSWORD in user_input:
                key = kwargs["key"] = lc7001.aio.hash_password(
                    user_input[CONF_PASSWORD].encode()
                )
            if CONF_PORT in user_input:  # for testing server emulation on localhost
                kwargs["port"] = user_input[CONF_PORT]
            task = self.hass.async_create_task(
                lc7001.aio.Connector(host, **kwargs).loop()
            )
            try:
                mac = await task
            except OSError:
                errors[CONF_HOST] = self.ERROR_INVALID_HOST
            except lc7001.aio.Authenticator.Error:
                errors[CONF_PASSWORD] = self.ERROR_INVALID_AUTH
            else:
                data = {CONF_HOST: host, CONF_MAC: mac}
                if key is not None:
                    data[CONF_AUTHENTICATION] = key.hex()
                return self.async_create_entry(title=host, data=data)

        # get user_input
        return self.async_show_form(
            step_id="user",
            data_schema=voluptuous.Schema(
                {
                    voluptuous.Required(CONF_HOST, default=host): str,
                    voluptuous.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle configuration by reauth."""
        host = self.context["unique_id"]
        errors = {CONF_PASSWORD: self.ERROR_INVALID_AUTH}
        if user_input is not None:
            key: bytes | None = None
            kwargs = {"key": key, "loop_timeout": -1}
            if CONF_AUTHENTICATION in user_input:
                key = kwargs["key"] = bytes.fromhex(user_input[CONF_AUTHENTICATION])
            if CONF_PORT in user_input:  # for testing server emulation on localhost
                kwargs["port"] = user_input[CONF_PORT]
            if CONF_PASSWORD in user_input:
                key = kwargs["key"] = lc7001.aio.hash_password(
                    user_input[CONF_PASSWORD].encode()
                )
            task = self.hass.async_create_task(
                lc7001.aio.Connector(host, **kwargs).loop()
            )
            try:
                mac = await task
            except OSError:
                errors[CONF_HOST] = self.ERROR_INVALID_HOST
            except lc7001.aio.Authenticator.Error:
                pass
            else:
                data = {CONF_HOST: host, CONF_MAC: mac}
                if CONF_PORT in user_input:  # for testing server emulation on localhost
                    data[CONF_PORT] = user_input[CONF_PORT]
                if key is not None:
                    data[CONF_AUTHENTICATION] = key.hex()
                entry = self.context["entry"]
                self.hass.config_entries.async_update_entry(entry, data=data)
                self.hass.async_create_task(
                    self.hass.config_entries.async_setup(entry.entry_id)
                )
                return self.async_abort(reason=self.ABORT_REAUTH_SUCCESSFUL)

        # get user_input
        return self.async_show_form(
            step_id="reauth",
            data_schema=voluptuous.Schema(
                {
                    voluptuous.Required(CONF_HOST, default=host): str,
                    voluptuous.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
