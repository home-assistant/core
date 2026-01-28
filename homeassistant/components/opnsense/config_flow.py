"""Config flow for OPNsense integration."""

from __future__ import annotations

import logging
from typing import Any

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    CONF_TRACKER_MAC_ADDRESSES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize URL by adding /api if missing."""
    url = url.rstrip("/")
    if not url.endswith("/api"):
        url = f"{url}/api"
    return url


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    url = data[CONF_URL]
    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]
    verify_ssl = data.get(CONF_VERIFY_SSL, False)

    if not url.startswith(("http://", "https://")):
        urls_to_try = [
            normalize_url(f"https://{url}"),
            normalize_url(f"http://{url}"),
        ]
    else:
        urls_to_try = [normalize_url(url)]

    last_error: Exception | None = None

    for test_url in urls_to_try:
        try:
            interface_client = diagnostics.InterfaceClient(
                api_key, api_secret, test_url, verify_ssl, timeout=20
            )
            await hass.async_add_executor_job(interface_client.get_arp)

            netinsight_client = diagnostics.NetworkInsightClient(
                api_key, api_secret, test_url, verify_ssl, timeout=20
            )
            interfaces = await hass.async_add_executor_job(
                netinsight_client.get_interfaces
            )

            data[CONF_URL] = test_url

            return {
                "title": f"OPNsense {test_url}",
                "interfaces": dict(interfaces),
            }
        except APIException as err:
            last_error = err
            continue
        except Exception as err:
            last_error = err
            continue

    if last_error:
        raise last_error
    raise APIException("Unable to connect to OPNsense")


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OPNsense."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._interfaces: dict[str, str] = {}
        self._devices: list[dict[str, Any]] = []
        self._interface_client: diagnostics.InterfaceClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except APIException as err:
                _LOGGER.debug("API exception during validation: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._interfaces = info["interfaces"]
                working_url = user_input[CONF_URL]
                self._interface_client = diagnostics.InterfaceClient(
                    user_input[CONF_API_KEY],
                    user_input[CONF_API_SECRET],
                    working_url,
                    user_input.get(CONF_VERIFY_SSL, False),
                    timeout=20,
                )
                self._user_input = {**user_input, CONF_URL: working_url}
                try:
                    devices = await self.hass.async_add_executor_job(
                        self._interface_client.get_arp
                    )
                    self._devices = devices
                except APIException:
                    errors["base"] = "cannot_fetch_devices"
                else:
                    return await self.async_step_interfaces()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_API_SECRET): str,
                vol.Optional(CONF_VERIFY_SSL, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_interfaces(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle interface selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_interfaces = user_input.get(CONF_TRACKER_INTERFACES, [])
            valid_interfaces = set(self._interfaces.values())
            if selected_interfaces:
                for interface in selected_interfaces:
                    if interface not in valid_interfaces:
                        errors["base"] = "invalid_interface"
                        break

            if not errors:
                self._selected_interfaces = selected_interfaces
                return await self.async_step_devices()

        interface_options = {
            description: f"{description} ({name})"
            if name != description
            else description
            for name, description in self._interfaces.items()
        }

        interface_select_options = [
            SelectOptionDict(value=key, label=label)
            for key, label in interface_options.items()
        ]

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=interface_select_options,
                        multiple=True,
                        translation_key="tracker_interfaces",
                        mode="list",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="interfaces",
            data_schema=data_schema,
            description_placeholders={
                "interfaces": ", ".join(self._interfaces.values())
            },
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device MAC address selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_macs = user_input.get(CONF_TRACKER_MAC_ADDRESSES, [])
            # Validate selected MAC addresses
            available_macs = {device["mac"] for device in self._devices}
            if selected_macs:
                for mac in selected_macs:
                    if mac not in available_macs:
                        errors["base"] = "invalid_mac"
                        break

            if not errors:
                data = {
                    CONF_URL: self._user_input[CONF_URL],
                    CONF_API_KEY: self._user_input[CONF_API_KEY],
                    CONF_API_SECRET: self._user_input[CONF_API_SECRET],
                    CONF_VERIFY_SSL: self._user_input.get(CONF_VERIFY_SSL, False),
                    CONF_TRACKER_INTERFACES: self._selected_interfaces,
                    CONF_TRACKER_MAC_ADDRESSES: selected_macs,
                }

                await self.async_set_unique_id(
                    f"{self._user_input[CONF_URL]}_{self._user_input[CONF_API_KEY]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"OPNsense {self._user_input[CONF_URL]}",
                    data=data,
                )

        device_options = {}
        for device in self._devices:
            mac = device["mac"]
            hostname = device.get("hostname") or "Unknown"
            ip = device.get("ip", "Unknown")
            interface = device.get("intf_description", "Unknown")
            if not self._selected_interfaces or interface in self._selected_interfaces:
                device_options[mac] = f"{mac} - {hostname} ({ip}) - {interface}"

        device_select_options = [
            SelectOptionDict(value=mac, label=label)
            for mac, label in device_options.items()
        ]

        if not device_options:
            data = {
                CONF_URL: self._user_input[CONF_URL],
                CONF_API_KEY: self._user_input[CONF_API_KEY],
                CONF_API_SECRET: self._user_input[CONF_API_SECRET],
                CONF_VERIFY_SSL: self._user_input.get(CONF_VERIFY_SSL, False),
                CONF_TRACKER_INTERFACES: self._selected_interfaces,
                CONF_TRACKER_MAC_ADDRESSES: [],
            }

            await self.async_set_unique_id(
                f"{self._user_input[CONF_URL]}_{self._user_input[CONF_API_KEY]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"OPNsense {self._user_input[CONF_URL]}",
                data=data,
            )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_TRACKER_MAC_ADDRESSES, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=device_select_options,
                        multiple=True,
                        translation_key="tracker_mac_addresses",
                        mode="list",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="devices",
            data_schema=data_schema,
            description_placeholders={
                "device_count": str(len(device_options)),
                "interface_count": str(len(self._selected_interfaces))
                if self._selected_interfaces
                else "all",
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        # Load existing configuration
        existing_url = reconfigure_entry.data[CONF_URL]
        existing_api_key = reconfigure_entry.data[CONF_API_KEY]
        existing_api_secret = reconfigure_entry.data[CONF_API_SECRET]
        existing_verify_ssl = reconfigure_entry.data.get(CONF_VERIFY_SSL, False)
        existing_interfaces = reconfigure_entry.data.get(CONF_TRACKER_INTERFACES, [])
        existing_mac_addresses = reconfigure_entry.data.get(
            CONF_TRACKER_MAC_ADDRESSES, []
        )

        # Initialize interface client with existing credentials
        try:
            interface_client = diagnostics.InterfaceClient(
                existing_api_key,
                existing_api_secret,
                existing_url,
                existing_verify_ssl,
                timeout=20,
            )
            # Test connection and get interfaces
            netinsight_client = diagnostics.NetworkInsightClient(
                existing_api_key,
                existing_api_secret,
                existing_url,
                existing_verify_ssl,
                timeout=20,
            )
            interfaces = await self.hass.async_add_executor_job(
                netinsight_client.get_interfaces
            )
            self._interfaces = dict(interfaces)

            # Get devices
            devices = await self.hass.async_add_executor_job(interface_client.get_arp)
            self._devices = devices
            self._interface_client = interface_client
        except APIException:
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="reconfigure",
                errors=errors,
            )

        # Start with interface selection
        return await self.async_step_reconfigure_interfaces()

    async def async_step_reconfigure_interfaces(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle interface reconfiguration step."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        existing_interfaces = reconfigure_entry.data.get(CONF_TRACKER_INTERFACES, [])

        if user_input is not None:
            selected_interfaces = user_input.get(CONF_TRACKER_INTERFACES, [])
            valid_interfaces = set(self._interfaces.values())
            if selected_interfaces:
                for interface in selected_interfaces:
                    if interface not in valid_interfaces:
                        errors["base"] = "invalid_interface"
                        break

            if not errors:
                self._selected_interfaces = selected_interfaces
                return await self.async_step_reconfigure_devices()

        interface_options = {
            description: f"{description} ({name})"
            if name != description
            else description
            for name, description in self._interfaces.items()
        }

        interface_select_options = [
            SelectOptionDict(value=key, label=label)
            for key, label in interface_options.items()
        ]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TRACKER_INTERFACES, default=existing_interfaces
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=interface_select_options,
                        multiple=True,
                        translation_key="tracker_interfaces",
                        mode="list",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure_interfaces",
            data_schema=data_schema,
            description_placeholders={
                "interfaces": ", ".join(self._interfaces.values())
            },
            errors=errors,
        )

    async def async_step_reconfigure_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device MAC address reconfiguration step."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        existing_mac_addresses = reconfigure_entry.data.get(
            CONF_TRACKER_MAC_ADDRESSES, []
        )

        if user_input is not None:
            selected_macs = user_input.get(CONF_TRACKER_MAC_ADDRESSES, [])
            available_macs = {device["mac"] for device in self._devices}
            invalid_macs = []
            if selected_macs:
                for mac in selected_macs:
                    if mac not in available_macs:
                        invalid_macs.append(mac)

            if invalid_macs:
                valid_selected_macs = [
                    mac for mac in selected_macs if mac in available_macs
                ]
                selected_macs = valid_selected_macs
                _LOGGER.warning(
                    "Some selected MAC addresses are no longer available and were removed: %s",
                    ", ".join(invalid_macs),
                )

            data_updates = {
                CONF_TRACKER_INTERFACES: self._selected_interfaces,
                CONF_TRACKER_MAC_ADDRESSES: selected_macs,
            }

            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates=data_updates,
            )

        device_options = {}
        available_macs = set()
        for device in self._devices:
            mac = device["mac"]
            hostname = device.get("hostname") or "Unknown"
            ip = device.get("ip", "Unknown")
            interface = device.get("intf_description", "Unknown")
            if not self._selected_interfaces or interface in self._selected_interfaces:
                device_options[mac] = f"{mac} - {hostname} ({ip}) - {interface}"
                available_macs.add(mac)

        valid_existing_macs = [
            mac for mac in existing_mac_addresses if mac in available_macs
        ]

        device_select_options = [
            SelectOptionDict(value=mac, label=label)
            for mac, label in device_options.items()
        ]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TRACKER_MAC_ADDRESSES, default=valid_existing_macs
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=device_select_options,
                        multiple=True,
                        translation_key="tracker_mac_addresses",
                        mode="list",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure_devices",
            data_schema=data_schema,
            description_placeholders={
                "device_count": str(len(device_options)),
                "interface_count": str(len(self._selected_interfaces))
                if self._selected_interfaces
                else "all",
            },
            errors=errors,
        )
