"""Config flow for swidget integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any
from urllib.parse import urlparse

from swidget.discovery import SwidgetDiscoveredDevice
from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import SwidgetDevice
import voluptuous as vol

from homeassistant.components import dhcp, ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import DiscoveryInfoType

from . import async_discover_devices
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = timedelta(minutes=15)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    device: SwidgetDevice = SwidgetDevice(
        host=data["host"],
        token_name="x-secret-key",
        secret_key=data.get("password"),
        use_https=True,
        use_websockets=False,
    )
    try:
        await device.update()
        await device.stop()
    except SwidgetException as exc:
        raise CannotConnect from exc
    return {
        "title": device.friendly_name,
        "mac_address": format_mac(device.mac_address),
    }


class SwidgetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for swidget."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, SwidgetDiscoveredDevice] = {}
        self._discovered_device: SwidgetDiscoveredDevice | None = None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        _LOGGER.debug("Swidget device found via DHCP: %s", discovery_info)
        return await self._async_handle_discovery(
            discovery_info.ip, format_mac(discovery_info.macaddress)
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via SSDP."""
        _LOGGER.debug("Swidget device found via SSDP: %s", discovery_info)
        discovered_ip = urlparse(discovery_info.ssdp_headers["location"]).hostname
        discovered_mac = format_mac(discovery_info.ssdp_headers["USN"].split("-")[-1])
        device_type = discovery_info.ssdp_headers["SERVER"].split(" ")[1].split("+")[0]
        insert_type = (
            discovery_info.ssdp_headers["SERVER"]
            .split(" ")[1]
            .split("+")[1]
            .split("/")[0]
        )
        friendly_name = discovery_info.ssdp_headers["SERVER"].split("/")[2].strip('"')
        return await self._async_handle_discovery(
            host=discovered_ip,
            mac=discovered_mac,
            device_type=device_type,
            insert_type=insert_type,
            friendly_name=friendly_name,
        )

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        return await self._async_handle_discovery(
            discovery_info[CONF_HOST], discovery_info[CONF_MAC]
        )

    async def _async_handle_discovery(
        self,
        host: str,
        mac: str,
        device_type: str = "Unknown",
        insert_type: str = "Unknown",
        friendly_name: str = "Unknown Swidget Device",
    ) -> ConfigFlowResult:
        """Handle any discovery."""
        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured()

        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")
        self._discovered_device = SwidgetDiscoveredDevice(
            mac, host, device_type, insert_type, friendly_name
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        if user_input is not None:
            user_input[CONF_HOST] = self._discovered_device.host
            info = await validate_input(self.hass, user_input)
            return self.async_create_entry(title=info["title"], data=user_input)

        self._set_confirm_only()
        placeholders = {
            "name": self._discovered_device.friendly_name,
            "host": self._discovered_device.host,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders=placeholders,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (user_input[CONF_HOST]):
                return await self.async_step_pick_device()
            try:
                info = await validate_input(self.hass, user_input)
                mac_address = info["mac_address"]
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unable to validate Swidget device credentials")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(mac_address))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            user_input[CONF_HOST] = self._discovered_devices[
                user_input[CONF_DEVICE]
            ].host
            info = await validate_input(self.hass, user_input)
            return self.async_create_entry(title=info["title"], data=user_input)

        configured_devices = {
            entry.unique_id for entry in self._async_current_entries()
        }
        self._discovered_devices = await async_discover_devices(self.hass)
        devices_name = {
            mac: f"{device.friendly_name} ({device.host})"
            for mac, device in self._discovered_devices.items()
            if mac not in configured_devices
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(devices_name),
                    vol.Required("password"): str,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
