"""Config flow for the Papouch integration."""

import asyncio
import logging
import re

import aiohttp
from aiopapouch import PapouchApiClient, create_device
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, WEB_MODE_INDEX
from .discovery import async_discover_papouch_devices

_LOGGER = logging.getLogger(__name__)


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
        client = PapouchApiClient(ip_address, session)

        try:
            await client.fetch_info()
            mode_device = await client.get_device_mode()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to connect to the device: %s", err)
            return {"base": "cannot_connect"}, None
        else:
            return {}, mode_device

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Discover the device from a DHCP request."""
        self.discovered_ip = discovery_info.ip

        for entry in self._async_current_entries():
            if entry.data.get("ip_address") == self.discovered_ip:
                return self.async_abort(reason="already_configured")

        discovered_mac = discovery_info.macaddress
        await self.async_set_unique_id(discovered_mac)
        self._abort_if_unique_id_configured(updates={"ip_address": self.discovered_ip})

        session = async_get_clientsession(self.hass)
        client = PapouchApiClient(self.discovered_ip, session)

        try:
            await asyncio.sleep(5)

            # create dummy device (DRY)

            device = await create_device(client)
            if device:
                self.discovered_name = f"{device.get_name()} ({device.get_location()}) - {self.discovered_ip}"
            else:
                return self.async_abort(reason="unsupported_device")
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to fetch device info after DHCP: %s", err)
            return self.async_abort(reason="cannot_connect")

        self.context.update({"title_placeholders": {"name": self.discovered_name}})

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None) -> ConfigFlowResult:
        """Step after adding the device via DHCP."""
        errors = {}

        if user_input is not None:
            user_input["ip_address"] = self.discovered_ip
            errors, mode_device = await self._test_connection(user_input["ip_address"])

            if not errors:
                self._saved_input = user_input
                if mode_device == -1:
                    return self.async_abort(reason="mode_is_missing")
                if mode_device != WEB_MODE_INDEX:
                    return await self.async_step_web_mode()

                return self.async_create_entry(
                    title=f"Papouch {user_input['ip_address']}", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
                    int, vol.Range(min=1, max=3600)
                ),
            }
        )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"name": self.discovered_name},
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step featuring active UDP discovery."""
        errors = {}

        if user_input is not None:
            if user_input["ip_address"] == "manual":
                self._saved_input = user_input
                return await self.async_step_manual()

            errors, mode_device = await self._test_connection(user_input["ip_address"])

            if not errors:
                self._saved_input = user_input
                if mode_device == -1:
                    return self.async_abort(reason="mode_is_missing")
                if mode_device != WEB_MODE_INDEX:
                    return await self.async_step_web_mode()

                return self.async_create_entry(
                    title=f"Papouch {user_input['ip_address']}", data=user_input
                )

        if self._discovered_ips is None:
            results = await async_discover_papouch_devices(self.hass)

            self._discovered_ips = {}
            for ip, device_info in results.items():
                location, name = device_info
                self._discovered_ips[ip] = f"{name} ({location}) - {ip}"

        if not self._discovered_ips and not self.discovered_ip and not errors:
            return await self.async_step_manual()

        options = self._discovered_ips.copy()

        if self.discovered_ip and self.discovered_ip not in options:
            options[self.discovered_ip] = f"Unknown device - {self.discovered_ip}"

        options["manual"] = "Enter IP manually"

        default_interval = (
            user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            if user_input
            else DEFAULT_SCAN_INTERVAL
        )

        schema = vol.Schema(
            {
                vol.Required("ip_address"): vol.In(options),
                vol.Required("scan_interval", default=default_interval): vol.All(
                    int, vol.Range(min=1, max=3600)
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_manual(self, user_input=None) -> ConfigFlowResult:
        """Handle manual IP entry when discovery fails or is bypassed."""
        errors = {}

        if user_input is not None:
            errors, mode_device = await self._test_connection(user_input["ip_address"])

            if not errors:
                self._saved_input = user_input
                if mode_device == -1:
                    return self.async_abort(reason="mode_is_missing")
                if mode_device != WEB_MODE_INDEX:
                    return await self.async_step_web_mode()

                return self.async_create_entry(
                    title=f"Papouch {user_input['ip_address']}", data=user_input
                )

        default_ip = self.discovered_ip or ""
        default_interval = DEFAULT_SCAN_INTERVAL

        if self._saved_input and "scan_interval" in self._saved_input:
            default_interval = self._saved_input["scan_interval"]
        if user_input and "scan_interval" in user_input:
            default_interval = user_input["scan_interval"]
        if user_input and "ip_address" in user_input:
            default_ip = user_input["ip_address"]

        schema = vol.Schema(
            {
                vol.Required("ip_address", default=default_ip): str,
                vol.Required("scan_interval", default=default_interval): vol.All(
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
        session = async_get_clientsession(self.hass)
        client = PapouchApiClient(self._saved_input["ip_address"], session)

        try:
            # Note that this is a dummy device and wouldn't be used later.
            # Used for DRY rule
            device = await create_device(client)

            if device is None:
                return self.async_abort(reason="unsupported_device")

            await device.switch_to_web_mode()

            return self.async_create_entry(
                title=f"Papouch {self._saved_input['ip_address']}",
                data=self._saved_input,
                description="web_mode_success",
            )
        except aiohttp.ClientError:
            return self.async_abort(reason="cannot_connect")

    async def async_step_abort_switch(self, user_input=None) -> ConfigFlowResult:
        """Action when user clicks cancel."""
        return self.async_abort(reason="web_mode_required")
