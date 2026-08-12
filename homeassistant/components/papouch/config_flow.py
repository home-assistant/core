"""Config flow for the Papouch integration."""

import asyncio
from collections.abc import Mapping
import ipaddress
import logging
import re
from typing import Any, override

import aiohttp
from aiopapouch import PapouchHTTPClient, create_device, is_device_supported
from aiopapouch.exceptions import DeviceAuthError, DeviceLogicError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import PapouchConfigEntry
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .discovery import async_discover_papouch_devices

_LOGGER = logging.getLogger(__name__)

WEB_MODE_INDEX = 3
DHCP_TIMEOUT = 5


class PapouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Papouch."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: PapouchConfigEntry | None = None
        self.discovered_ip: str | None = None
        self.discovered_name: str | None = None
        self._saved_input: dict | None = None
        self._discovered_ips: dict[str, str] | None = None

    async def _test_connection(
        self, ip_address: str, password: str = ""
    ) -> tuple[dict[str, str], int | None]:
        """Test the connection and return any errors and the device mode."""

        if not re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", ip_address):
            return {"ip_address": "invalid_ip_format"}, None

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(ip_address, session, password=password)

        try:
            await client.fetch_info()
            mode_device = await client.get_device_mode()
        except DeviceAuthError:
            return {"base": "invalid_auth"}, None
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to connect to the device: %s", err)
            return {"base": "cannot_connect"}, None
        else:
            return {}, mode_device

    async def _get_device_name(self, ip_address: str, password: str = "") -> str:
        """Fetch the real device name and location directly from the device."""
        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(ip_address, session, password=password)
        try:
            name, location = await client.get_device_info()
            if name and location:
                return f"{name} ({location})"
        except aiohttp.ClientError:
            pass

        return "Papouch Device"

    async def _async_process_user_input(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], ConfigFlowResult | None]:
        """Process user input, test connection, and determine the next routing step."""

        for entry in self._async_current_entries():
            if entry.data.get("ip_address") == user_input["ip_address"]:
                return {}, self.async_abort(reason="already_configured")

        ip_address = user_input["ip_address"]
        password = str(user_input.get("password", ""))
        errors, mode_device = await self._test_connection(
            user_input["ip_address"], password
        )

        if not errors:
            self._saved_input = user_input
            if mode_device == -1:
                return {}, self.async_abort(reason="mode_is_missing")
            if mode_device != WEB_MODE_INDEX:
                return {}, await self.async_step_web_mode()

            session = async_get_clientsession(self.hass)
            client = PapouchHTTPClient(ip_address, session, password=password)

            title_name = await self._get_device_name(ip_address, password)

            try:
                mac_address = await client.get_device_mac()
            except aiohttp.ClientError, DeviceLogicError:
                return {"base": "cannot_connect"}, None

            if mac_address:
                formatted_mac = format_mac(mac_address)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()

            data = {
                "ip_address": user_input["ip_address"],
                "password": password,
                "device_name": title_name,
            }
            options = {
                "refresh_rate": user_input.get("refresh_rate", DEFAULT_SCAN_INTERVAL)
            }

            return {}, self.async_create_entry(
                title=f"{title_name} - {user_input['ip_address']}",
                data=data,
                options=options,
            )

        return errors, None

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Discover the device from a DHCP request."""

        self.discovered_ip = discovery_info.ip
        discovered_mac = format_mac(discovery_info.macaddress)

        await self.async_set_unique_id(discovered_mac)

        for entry in self._async_current_entries():
            if entry.unique_id == discovered_mac:
                if entry.data.get("ip_address") != self.discovered_ip:
                    base_title = (
                        entry.title.rsplit(" - ", 1)[0]
                        if " - " in entry.title
                        else entry.title
                    )
                    new_title = f"{base_title} - {self.discovered_ip}"

                    updated_data = {
                        **entry.data,
                        "ip_address": self.discovered_ip,
                    }

                    self.hass.config_entries.async_update_entry(
                        entry, data=updated_data, title=new_title
                    )

                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )

                return self.async_abort(reason="already_configured")

            if (
                entry.unique_id is None
                and entry.data.get("ip_address") == self.discovered_ip
            ):
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=discovered_mac
                )
                return self.async_abort(reason="already_configured")

        session = async_get_clientsession(self.hass)
        client = PapouchHTTPClient(self.discovered_ip, session)

        try:
            await asyncio.sleep(DHCP_TIMEOUT)
            device_name, device_location = await client.get_device_info()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to fetch device info after DHCP: %s", err)
            return self.async_abort(reason="cannot_connect")

        if not is_device_supported(device_name):
            return self.async_abort(reason="unsupported_device")

        title_name = f"{device_name} ({device_location})"
        self.discovered_name = f"{title_name} - {self.discovered_ip}"

        self.context.update({"title_placeholders": {"name": self.discovered_name}})

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                vol.Optional("password"): str,
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
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                vol.Optional("password"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                vol.Optional("password"): str,
            }
        )

        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_web_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step where the user can switch the device into WEB mode via buttons."""
        return self.async_show_menu(
            step_id="web_mode", menu_options=["execute_switch", "abort_switch"]
        )

    async def async_step_execute_switch(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Action when user clicks the switch button."""

        assert self._saved_input is not None

        session = async_get_clientsession(self.hass)
        password = self._saved_input.get("password", "")
        ip_address = self._saved_input["ip_address"]

        client = PapouchHTTPClient(ip_address, session, password=password)

        try:
            device = await create_device(client)

            if device is None:
                return self.async_abort(reason="unsupported_device")

            await device.switch_to_web_mode()

            title_name = await self._get_device_name(ip_address, password)

            try:
                mac_address = await client.get_device_mac()
            except aiohttp.ClientError, DeviceLogicError:
                return self.async_abort(reason="cannot_connect")

            if mac_address:
                formatted_mac = format_mac(mac_address)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()

            data = {
                "ip_address": ip_address,
                "password": password,
                "device_name": title_name,
            }
            options = {
                "refresh_rate": self._saved_input.get(
                    "refresh_rate", DEFAULT_SCAN_INTERVAL
                )
            }

            return self.async_create_entry(
                title=f"{title_name} - {ip_address}",
                data=data,
                options=options,
                description="web_mode_success",
            )
        except aiohttp.ClientError:
            return self.async_abort(reason="cannot_connect")

    async def async_step_abort_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Action when user clicks cancel."""
        return self.async_abort(reason="web_mode_required")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None and self._reauth_entry:
            password = user_input.get("password", "")
            ip_address = self._reauth_entry.data["ip_address"]

            errors, _ = await self._test_connection(ip_address, password)

            if not errors:
                new_data = {**self._reauth_entry.data, "password": password}
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=new_data
                )

                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)

                return self.async_abort(reason="reauth_successful")

        device_name = self._reauth_entry.title if self._reauth_entry else "Papouch"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional("password"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "ip_address": self._reauth_entry.data["ip_address"]
                if self._reauth_entry
                else "",
                "name": device_name,
            },
        )

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: PapouchConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return PapouchOptionsFlowHandler()


class PapouchOptionsFlowHandler(OptionsFlow):
    """Handle Papouch options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_refresh = self.config_entry.options.get(
            "refresh_rate", DEFAULT_SCAN_INTERVAL
        )

        schema = vol.Schema(
            {
                vol.Required("refresh_rate", default=current_refresh): vol.All(
                    int, vol.Range(min=1, max=3600)
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
