"""Config flow for WiZ Platform."""

from __future__ import annotations

import logging
from typing import Any

from pywizlight import wizlight
from pywizlight.discovery import DiscoveredBulb
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError
import voluptuous as vol

from homeassistant.components import dhcp, onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.util.network import is_ip_address

from .const import DEFAULT_NAME, DISCOVER_SCAN_TIMEOUT, DOMAIN, WIZ_CONNECT_EXCEPTIONS
from .discovery import async_discover_devices
from .utils import _short_mac, name_from_bulb_type_and_mac

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"


class WizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiZ."""

    VERSION = 1

    _discovered_device: DiscoveredBulb
    _name: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, DiscoveredBulb] = {}

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = DiscoveredBulb(
            discovery_info.ip, discovery_info.macaddress
        )
        return await self._async_handle_discovery()

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, str]
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        self._discovered_device = DiscoveredBulb(
            discovery_info["ip_address"], discovery_info["mac_address"]
        )
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> ConfigFlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        _LOGGER.debug("Discovered device: %s", device)
        ip_address = device.ip_address
        mac = device.mac_address
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: ip_address})
        await self._async_connect_discovered_or_abort()
        return await self.async_step_discovery_confirm()

    async def _async_connect_discovered_or_abort(self) -> None:
        """Connect to the device and verify its responding."""
        device = self._discovered_device
        bulb = wizlight(device.ip_address)
        try:
            bulbtype = await bulb.get_bulbtype()
        except WIZ_CONNECT_EXCEPTIONS as ex:
            _LOGGER.debug(
                "Failed to connect to %s during discovery: %s",
                device.ip_address,
                ex,
                exc_info=True,
            )
            raise AbortFlow("cannot_connect") from ex
        self._name = name_from_bulb_type_and_mac(bulbtype, device.mac_address)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        ip_address = self._discovered_device.ip_address
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            # Make sure the device is still there and
            # update the name if the firmware has auto
            # updated since discovery
            await self._async_connect_discovered_or_abort()
            return self.async_create_entry(
                title=self._name,
                data={CONF_HOST: ip_address},
            )

        self._set_confirm_only()
        placeholders = {"name": self._name, "host": ip_address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            device = self._discovered_devices[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(device.mac_address, raise_on_progress=False)
            bulb = wizlight(device.ip_address)
            try:
                bulbtype = await bulb.get_bulbtype()
            except WIZ_CONNECT_EXCEPTIONS:
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(
                title=name_from_bulb_type_and_mac(bulbtype, device.mac_address),
                data={CONF_HOST: device.ip_address},
            )

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        discovered_devices = await async_discover_devices(
            self.hass, DISCOVER_SCAN_TIMEOUT
        )
        self._discovered_devices = {
            device.mac_address: device for device in discovered_devices
        }
        devices_name = {
            mac: f"{DEFAULT_NAME} {_short_mac(mac)} ({device.ip_address})"
            for mac, device in self._discovered_devices.items()
            if mac not in current_unique_ids and device.ip_address not in current_hosts
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            if not (host := user_input[CONF_HOST]):
                return await self.async_step_pick_device()
            if not is_ip_address(user_input[CONF_HOST]):
                errors["base"] = "no_ip"
            else:
                bulb = wizlight(host)
                try:
                    bulbtype = await bulb.get_bulbtype()
                    mac = await bulb.getMac()
                except WizLightTimeOutError:
                    errors["base"] = "bulb_time_out"
                except ConnectionRefusedError:
                    errors["base"] = "cannot_connect"
                except WizLightConnectionError:
                    errors["base"] = "no_wiz_light"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(mac, raise_on_progress=False)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: user_input[CONF_HOST]}
                    )
                    name = name_from_bulb_type_and_mac(bulbtype, mac)
                    return self.async_create_entry(
                        title=name,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
        )
