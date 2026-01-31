"""Config flow for Lyngdorf Integration."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from ipaddress import IPv6Address, ip_address
import logging
from typing import Any, cast
from urllib.parse import urlparse

from async_upnp_client.profiles.dlna import DmrDevice
from getmac import get_mac_address
from lyngdorf.const import LyngdorfModel
from lyngdorf.device import async_find_receiver_model
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_MANUFACTURER,
    CONF_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    SUPPORTED_MANUFACTURERS,
)

_LOGGER = logging.getLogger(__name__)

FlowInput = Mapping[str, Any] | None


class LyngdorfFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Lyngdorf config flow the mac address is used for the device ID."""

    def __init__(self) -> None:
        """Initialize flow."""
        self._discoveries: dict[str, ssdp.SsdpServiceInfo] = {}
        self._location: str | None = None
        # self._id: str | None = None
        self._device_manufacturer: str | None = None
        # self._device_type: str | None = None
        self._device_model: str | None = None
        self._device_serial_number: str | None = None
        self._name: str | None = None
        self._mac: str | None = None
        self._host: str
        self._options: dict[str, Any] = {}

    async def async_step_user(self, user_input: FlowInput = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user.

        Let user choose from a list of found and unconfigured devices or to
        enter an URL manually.
        """

        if user_input is not None:
            if not (name := user_input.get(CONF_NAME)):
                # No device chosen, user might want to directly enter an URL
                return await self.async_step_manual()
            # User has chosen a device, ask for confirmation
            discovery = self._discoveries[name]
            await self._async_set_info_from_discovery(discovery)
            return await self._create_entry()

        if not (discoveries := await self._async_get_discoveries()):
            # Nothing found, maybe the user knows an URL to try
            return await self.async_step_manual()

        self._discoveries = {
            discovery.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or cast(str, urlparse(discovery.ssdp_location).hostname): discovery
            for discovery in discoveries
        }

        data_schema = vol.Schema(
            {vol.Optional(CONF_NAME): vol.In(self._discoveries.keys())}
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_manual(self, user_input: FlowInput = None) -> ConfigFlowResult:
        """Manual URL entry by the user."""
        errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]

            try:
                model: LyngdorfModel = await async_find_receiver_model(
                    self._host
                )  # This opens and closes a TCP socket, so therefore updates the ARP table
                self._device_model = model.model
                self._mac = await _async_get_mac_address(
                    self.hass, self._host
                )  # Depends on the ARP table being up to date

                if not self._mac:
                    errors["base"] = "no_mac"
                else:
                    self._device_manufacturer = model.manufacturer

                    await self.async_set_unique_id(self._mac)
                    self._abort_if_unique_id_configured()

                    return await self._create_entry()

            except TimeoutError:
                errors["base"] = "timeout_connect"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=False): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_DEVICE_NAME): cv.string,
            }
        )

        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by SSDP discovery."""

        await self._async_set_info_from_discovery(discovery_info)

        # Abort if another config entry has the same location or MAC address, in
        # case the device doesn't have a static and unique UDN (breaking the
        # UPnP spec).
        for entry in self._async_current_entries(include_ignore=True):
            if self._mac and self._mac == entry.data.get(CONF_MAC):
                return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {"name": self._name or "Lyngdorf"}

        return await self.async_step_confirm()

    async def async_step_ignore(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Ignore this config flow."""
        self._mac = user_input["unique_id"]
        assert self._mac
        await self.async_set_unique_id(self._mac, raise_on_progress=False)

        return self.async_create_entry(
            title=user_input["title"],
            data={
                CONF_DEVICE_ID: self._mac,
                # CONF_TYPE: self._device_type,
                CONF_MAC: self._mac,
                CONF_MODEL: self._device_model,
                CONF_MANUFACTURER: self._device_manufacturer,
                CONF_SERIAL_NUMBER: self._device_serial_number,
                CONF_HOST: urlparse(self._location).hostname,
            },
        )

    async def async_step_unignore(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Rediscover previously ignored devices by their unique_id."""
        self._mac = user_input["unique_id"]
        assert self._mac
        await self.async_set_unique_id(self._mac)

        self.context["title_placeholders"] = {"name": self._name or "Lyngdorf"}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: FlowInput = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        _LOGGER.debug("async_step_confirm: %s", user_input)

        if user_input is not None:
            return await self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def _create_entry(self) -> ConfigFlowResult:
        """Create a config entry, assuming all required information is now known."""
        title: str
        if self._location:
            title = "" + (
                self._name or urlparse(self._location).hostname or DEFAULT_DEVICE_NAME
            )
        else:
            title = self._name or DEFAULT_DEVICE_NAME

        assert self._mac

        data = {
            CONF_DEVICE_ID: self._mac,
            # CONF_TYPE: self._device_type,
            CONF_MAC: self._mac,
            CONF_MODEL: self._device_model,
            CONF_MANUFACTURER: self._device_manufacturer,
            CONF_SERIAL_NUMBER: self._device_serial_number,
            CONF_HOST: self._host,
        }
        await self.async_set_unique_id(self._mac)
        return self.async_create_entry(title=title, data=data, options=self._options)

    async def _async_set_info_from_discovery(
        self, discovery_info: ssdp.SsdpServiceInfo, abort_if_configured: bool = True
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""

        if not self._location:
            self._location = discovery_info.ssdp_location
            assert isinstance(self._location, str)

        self._mac = await _async_get_mac_address(self.hass, self._host)

        await self.async_set_unique_id(self._mac, raise_on_progress=abort_if_configured)

        self._device_model = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME) or ""
        self._device_serial_number = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_SERIAL) or ""
        ).lower()
        self._device_manufacturer = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER) or ""
        )

        # self._device_type = discovery_info.ssdp_nt or discovery_info.ssdp_st
        self._name = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_DEVICE_NAME
        )
        self._host = str(
            discovery_info.ssdp_headers.get("_host")
            or urlparse(self._location).hostname
        )

        if abort_if_configured:
            self._abort_if_unique_id_configured(reload_on_update=False)

    async def _async_get_discoveries(self) -> list[ssdp.SsdpServiceInfo]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""

        # Get all compatible devices from ssdp's cache
        discoveries: list[ssdp.SsdpServiceInfo] = []
        for udn_st in DmrDevice.DEVICE_TYPES:
            st_discoveries = await ssdp.async_get_discovery_info_by_st(
                self.hass, udn_st
            )
            discoveries.extend(st_discoveries)

        # Filter out devices already configured
        current_unique_ids = {
            entry.unique_id
            for entry in self._async_current_entries(include_ignore=False)
        }
        discoveries = [
            disc for disc in discoveries if disc.ssdp_udn not in current_unique_ids
        ]

        return [disc for disc in discoveries if _is_lyngdorf_device(disc)]


def _is_lyngdorf_device(discovery_info: ssdp.SsdpServiceInfo) -> bool:
    # Special cases for devices with other discovery methods (e.g. mDNS), or
    # that advertise multiple unrelated (sent in separate discovery packets)
    # UPnP devices.
    manufacturer = (discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER) or "").lower()

    if manufacturer in map(str.lower, SUPPORTED_MANUFACTURERS):
        # one of ours
        return True

    return False


async def _async_get_mac_address(hass: HomeAssistant, host: str) -> str | None:
    """Get mac address from host name, IPv4 address, or IPv6 address."""
    # Help mypy, which has trouble with the async_add_executor_job + partial call
    mac_address: str | None
    # getmac has trouble using IPv6 addresses as the "hostname" parameter so
    # assume host is an IP address, then handle the case it's not.
    try:
        ip_addr = ip_address(host)
    except ValueError:
        mac_address = await hass.async_add_executor_job(
            partial(get_mac_address, hostname=host)
        )
    else:
        if ip_addr.version == 4:
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, ip=host)
            )
        else:
            # Drop scope_id from IPv6 address by converting via int
            ip_addr = IPv6Address(int(ip_addr))
            mac_address = await hass.async_add_executor_job(
                partial(get_mac_address, ip6=str(ip_addr))
            )

    if not mac_address:
        return None

    return dr.format_mac(mac_address)


class ConnectError(HomeAssistantError):
    """Error occurred when trying to connect to a device."""
