"""Config flow for the Papouch integration."""

import asyncio
import ipaddress
import logging
import re
from typing import override

import aiohttp
from aiopapouch import PapouchHTTPClient, create_device
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .discovery import async_discover_papouch_devices

_LOGGER = logging.getLogger(__name__)

WEB_MODE_INDEX = 3
DHCP_TIMEOUT = 5


class PapouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Papouch."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_ip: str | None = None
        self.discovered_name: str | None = None
        self._saved_input: dict | None = None
        self._discovered_ips: dict[str, str] | None = None

    async def _test_connection(
        self, ip_address: str
    ) -> tuple[dict[str, str], int | None]:
        """Test the connection and return any errors and the device mode."""

        if not re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", ip_address):
            return {"ip_address": "invalid_ip_format"}, None

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(ip_address, session)

        try:
            await client.fetch_info()
            mode_device = await client.get_device_mode()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to connect to the device: %s", err)
            return {"base": "cannot_connect"}, None
        else:
            return {}, mode_device

    async def _async_process_user_input(
        self, user_input: dict
    ) -> tuple[dict[str, str], ConfigFlowResult | None]:
        """Process user input, test connection, and determine the next routing step."""

        for entry in self._async_current_entries():
            if entry.data.get("ip_address") == user_input["ip_address"]:
                return {}, self.async_abort(reason="already_configured")

        errors, mode_device = await self._test_connection(user_input["ip_address"])

        if not errors:
            self._saved_input = user_input
            if mode_device == -1:
                return {}, self.async_abort(reason="mode_is_missing")
            if mode_device != WEB_MODE_INDEX:
                return {}, await self.async_step_web_mode()

            return {}, self.async_create_entry(
                title=f"Papouch ({user_input['ip_address']})", data=user_input
            )

        return errors, None

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Discover the device from a DHCP request.

        After finding some device HA will immediately send a "discovery" message
        to create a device instatnce, but at that moment the device can have turned off
        the WEB server and suppose that 5 seconds is enough for the device to activate it.
        """

        self.discovered_ip = discovery_info.ip

        for entry in self._async_current_entries():
            if entry.data.get("ip_address") == self.discovered_ip:
                return self.async_abort(reason="already_configured")

        discovered_mac = discovery_info.macaddress
        await self.async_set_unique_id(discovered_mac)
        self._abort_if_unique_id_configured(updates={"ip_address": self.discovered_ip})

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(self.discovered_ip, session)

        try:
            await asyncio.sleep(DHCP_TIMEOUT)
            device = await create_device(client)
            if device:
                self.discovered_name = (
                    f"{device.name} ({device.location}) - {self.discovered_ip}"
                )
            else:
                return self.async_abort(reason="unsupported_device")
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to fetch device info after DHCP: %s", err)
            return self.async_abort(reason="cannot_connect")

        self.context.update({"title_placeholders": {"name": self.discovered_name}})

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None) -> ConfigFlowResult:
        """Step after adding the device via DHCP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input["ip_address"] = self.discovered_ip
            errors, result = await self._async_process_user_input(user_input)
            if result:
                return result

        schema = vol.Schema(
            {
                vol.Required("refresh_rate", default=DEFAULT_SCAN_INTERVAL): vol.All(
                    int, vol.Range(min=1, max=3600)
                ),
            }
        )

        assert self.discovered_name is not None

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"name": self.discovered_name},
        )

    @override
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step featuring active UDP discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input["ip_address"] == "manual":
                self._saved_input = user_input
                return await self.async_step_manual()

            errors, result = await self._async_process_user_input(user_input)
            if result:
                return result

        if self._discovered_ips is None:
            results = await async_discover_papouch_devices(self.hass)

            configured_ips = {
                entry.data.get("ip_address")
                for entry in self._async_current_entries()
                if entry.data.get("ip_address")
            }

            filtered_results = {
                ip: data for ip, data in results.items() if ip not in configured_ips
            }

            sorted_ips = sorted(filtered_results.keys(), key=ipaddress.ip_address)
            self._discovered_ips = {}

            for ip in sorted_ips:
                location, name = filtered_results[ip]
                self._discovered_ips[ip] = f"{ip} - {name} ({location})"

        if not self._discovered_ips and not self.discovered_ip and not errors:
            return await self.async_step_manual()

        options = self._discovered_ips.copy()

        if self.discovered_ip and self.discovered_ip not in options:
            options[self.discovered_ip] = f"Unknown device - {self.discovered_ip}"

        options["manual"] = "Enter IP manually"

        default_interval = (
            user_input.get("refresh_rate", DEFAULT_SCAN_INTERVAL)
            if user_input
            else DEFAULT_SCAN_INTERVAL
        )

        schema = vol.Schema(
            {
                vol.Required("ip_address"): vol.In(options),
                vol.Required("refresh_rate", default=default_interval): vol.All(
                    int, vol.Range(min=1, max=3600)
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_manual(self, user_input=None) -> ConfigFlowResult:
        """Handle manual IP entry when discovery fails or is bypassed."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, result = await self._async_process_user_input(user_input)
            if result:
                return result

        default_ip = self.discovered_ip or ""
        default_interval = DEFAULT_SCAN_INTERVAL

        if self._saved_input and "refresh_rate" in self._saved_input:
            default_interval = self._saved_input["refresh_rate"]
        if user_input and "refresh_rate" in user_input:
            default_interval = user_input["refresh_rate"]
        if user_input and "ip_address" in user_input:
            default_ip = user_input["ip_address"]

        schema = vol.Schema(
            {
                vol.Required("ip_address", default=default_ip): str,
                vol.Required("refresh_rate", default=default_interval): vol.All(
                    int, vol.Range(min=1, max=3600)
                ),
            }
        )

        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_web_mode(self, user_input=None) -> ConfigFlowResult:
        """Step where the user can switch the device into WEB mode via buttons."""
        return self.async_show_menu(
            step_id="web_mode", menu_options=["execute_switch", "abort_switch"]
        )

    async def async_step_execute_switch(self, user_input=None) -> ConfigFlowResult:
        """Action when user clicks the switch button."""

        assert self._saved_input is not None

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(self._saved_input["ip_address"], session)

        try:
            device = await create_device(client)

            if device is None:
                return self.async_abort(reason="unsupported_device")

            await device.switch_to_web_mode()

            return self.async_create_entry(
                title=f"Papouch ({self._saved_input['ip_address']})",
                data=self._saved_input,
                description="web_mode_success",
            )
        except aiohttp.ClientError:
            return self.async_abort(reason="cannot_connect")

    async def async_step_abort_switch(self, user_input=None) -> ConfigFlowResult:
        """Action when user clicks cancel."""
        return self.async_abort(reason="web_mode_required")
