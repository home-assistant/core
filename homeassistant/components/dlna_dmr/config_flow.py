"""Config flow for DLNA DMR."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from ipaddress import IPv6Address, ip_address
import logging
from pprint import pformat
from typing import Any, cast
from urllib.parse import urlparse

from async_upnp_client.client import UpnpError
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.profiles.profile import find_device_of_type
from getmac import get_mac_address
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MAC, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import IntegrationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_BROWSE_UNFILTERED,
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DEFAULT_NAME,
    DOMAIN,
)
from .data import get_domain_data

LOGGER = logging.getLogger(__name__)

FlowInput = Mapping[str, Any] | None


class ConnectError(IntegrationError):
    """Error occurred when trying to connect to a device."""


class DlnaDmrFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a DLNA DMR config flow.

    The Unique Device Name (UDN) of the DMR device is used as the unique_id for
    config entries and for entities. This UDN may differ from the root UDN if
    the DMR is an embedded device.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._discoveries: dict[str, ssdp.SsdpServiceInfo] = {}
        self._location: str | None = None
        self._udn: str | None = None
        self._device_type: str | None = None
        self._name: str | None = None
        self._mac: str | None = None
        self._options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Define the config flow to handle options."""
        return DlnaDmrOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: FlowInput = None) -> FlowResult:
        """Handle a flow initialized by the user.

        Let user choose from a list of found and unconfigured devices or to
        enter an URL manually.
        """
        LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None:
            if not (host := user_input.get(CONF_HOST)):
                # No device chosen, user might want to directly enter an URL
                return await self.async_step_manual()
            # User has chosen a device, ask for confirmation
            discovery = self._discoveries[host]
            await self._async_set_info_from_discovery(discovery)
            return self._create_entry()

        if not (discoveries := await self._async_get_discoveries()):
            # Nothing found, maybe the user knows an URL to try
            return await self.async_step_manual()

        self._discoveries = {
            discovery.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or cast(str, urlparse(discovery.ssdp_location).hostname): discovery
            for discovery in discoveries
        }

        data_schema = vol.Schema(
            {vol.Optional(CONF_HOST): vol.In(self._discoveries.keys())}
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_manual(self, user_input: FlowInput = None) -> FlowResult:
        """Manual URL entry by the user."""
        LOGGER.debug("async_step_manual: user_input: %s", user_input)

        # Device setup manually, assume we don't get SSDP broadcast notifications
        self._options[CONF_POLL_AVAILABILITY] = True

        errors = {}
        if user_input is not None:
            self._location = user_input[CONF_URL]
            try:
                await self._async_connect()
            except ConnectError as err:
                errors["base"] = err.args[0]
            else:
                return self._create_entry()

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=errors
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        LOGGER.debug("async_step_ssdp: discovery_info %s", pformat(discovery_info))

        await self._async_set_info_from_discovery(discovery_info)

        if _is_ignored_device(discovery_info):
            return self.async_abort(reason="alternative_integration")

        # Abort if the device doesn't support all services required for a DmrDevice.
        if not _is_dmr_device(discovery_info):
            return self.async_abort(reason="not_dmr")

        # Abort if another config entry has the same location or MAC address, in
        # case the device doesn't have a static and unique UDN (breaking the
        # UPnP spec).
        for entry in self._async_current_entries(include_ignore=True):
            if self._location == entry.data[CONF_URL]:
                return self.async_abort(reason="already_configured")
            if self._mac and self._mac == entry.data.get(CONF_MAC):
                return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {"name": self._name}

        return await self.async_step_confirm()

    async def async_step_ignore(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Ignore this config flow, and add MAC address as secondary identifier.

        Not all DMR devices correctly implement the spec, so their UDN may
        change between boots. Use the MAC address as a secondary identifier so
        they can still be ignored in this case.
        """
        LOGGER.debug("async_step_ignore: user_input: %s", user_input)
        self._udn = user_input["unique_id"]
        assert self._udn
        await self.async_set_unique_id(self._udn, raise_on_progress=False)

        # Try to get relevant info from SSDP discovery, but don't worry if it's
        # not available - the data values will just be None in that case
        for dev_type in DmrDevice.DEVICE_TYPES:
            discovery = await ssdp.async_get_discovery_info_by_udn_st(
                self.hass, self._udn, dev_type
            )
            if discovery:
                await self._async_set_info_from_discovery(
                    discovery, abort_if_configured=False
                )
                break

        return self.async_create_entry(
            title=user_input["title"],
            data={
                CONF_URL: self._location,
                CONF_DEVICE_ID: self._udn,
                CONF_TYPE: self._device_type,
                CONF_MAC: self._mac,
            },
        )

    async def async_step_unignore(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Rediscover previously ignored devices by their unique_id."""
        LOGGER.debug("async_step_unignore: user_input: %s", user_input)
        self._udn = user_input["unique_id"]
        assert self._udn
        await self.async_set_unique_id(self._udn)

        # Find a discovery matching the unignored unique_id for a DMR device
        for dev_type in DmrDevice.DEVICE_TYPES:
            discovery = await ssdp.async_get_discovery_info_by_udn_st(
                self.hass, self._udn, dev_type
            )
            if discovery:
                break
        else:
            return self.async_abort(reason="discovery_error")

        await self._async_set_info_from_discovery(discovery, abort_if_configured=False)

        self.context["title_placeholders"] = {"name": self._name}

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: FlowInput = None) -> FlowResult:
        """Allow the user to confirm adding the device."""
        LOGGER.debug("async_step_confirm: %s", user_input)

        if user_input is not None:
            return self._create_entry()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def _async_connect(self) -> None:
        """Connect to a device to confirm it works and gather extra information.

        Updates this flow's unique ID to the device UDN if not already done.
        Raises ConnectError if something goes wrong.
        """
        LOGGER.debug("_async_connect: location: %s", self._location)
        assert self._location, "self._location has not been set before connect"

        domain_data = get_domain_data(self.hass)
        try:
            device = await domain_data.upnp_factory.async_create_device(self._location)
        except UpnpError as err:
            raise ConnectError("cannot_connect") from err

        if not DmrDevice.is_profile_device(device):
            raise ConnectError("not_dmr")

        device = find_device_of_type(device, DmrDevice.DEVICE_TYPES)

        if not self._udn:
            self._udn = device.udn
            await self.async_set_unique_id(self._udn)

        # Abort if already configured, but update the last-known location
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self._location}, reload_on_update=False
        )

        if not self._device_type:
            self._device_type = device.device_type

        if not self._name:
            self._name = device.name

        if not self._mac and (host := urlparse(self._location).hostname):
            self._mac = await _async_get_mac_address(self.hass, host)

    def _create_entry(self) -> FlowResult:
        """Create a config entry, assuming all required information is now known."""
        LOGGER.debug(
            "_async_create_entry: location: %s, UDN: %s", self._location, self._udn
        )
        assert self._location
        assert self._udn
        assert self._device_type

        title = self._name or urlparse(self._location).hostname or DEFAULT_NAME
        data = {
            CONF_URL: self._location,
            CONF_DEVICE_ID: self._udn,
            CONF_TYPE: self._device_type,
            CONF_MAC: self._mac,
        }
        return self.async_create_entry(title=title, data=data, options=self._options)

    async def _async_set_info_from_discovery(
        self, discovery_info: ssdp.SsdpServiceInfo, abort_if_configured: bool = True
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""
        LOGGER.debug(
            "_async_set_info_from_discovery: location: %s, UDN: %s",
            discovery_info.ssdp_location,
            discovery_info.ssdp_udn,
        )

        if not self._location:
            self._location = discovery_info.ssdp_location
            assert isinstance(self._location, str)

        self._udn = discovery_info.ssdp_udn
        await self.async_set_unique_id(self._udn, raise_on_progress=abort_if_configured)

        self._device_type = discovery_info.ssdp_nt or discovery_info.ssdp_st
        self._name = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or urlparse(self._location).hostname
            or DEFAULT_NAME
        )

        if host := discovery_info.ssdp_headers.get("_host"):
            self._mac = await _async_get_mac_address(self.hass, host)

        if abort_if_configured:
            # Abort if already configured, but update the last-known location
            updates = {CONF_URL: self._location}
            # Set the MAC address for older entries
            if self._mac:
                updates[CONF_MAC] = self._mac
            self._abort_if_unique_id_configured(updates=updates, reload_on_update=False)

    async def _async_get_discoveries(self) -> list[ssdp.SsdpServiceInfo]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""
        LOGGER.debug("_get_discoveries")

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

        return discoveries


class DlnaDmrOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a DLNA DMR options flow.

    Configures the single instance and updates the existing config entry.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        # Don't modify existing (read-only) options -- copy and update instead
        options = dict(self.config_entry.options)

        if user_input is not None:
            LOGGER.debug("user_input: %s", user_input)
            listen_port = user_input.get(CONF_LISTEN_PORT) or None
            callback_url_override = user_input.get(CONF_CALLBACK_URL_OVERRIDE) or None

            try:
                # Cannot use cv.url validation in the schema itself so apply
                # extra validation here
                if callback_url_override:
                    cv.url(callback_url_override)
            except vol.Invalid:
                errors["base"] = "invalid_url"

            options[CONF_LISTEN_PORT] = listen_port
            options[CONF_CALLBACK_URL_OVERRIDE] = callback_url_override
            options[CONF_POLL_AVAILABILITY] = user_input[CONF_POLL_AVAILABILITY]
            options[CONF_BROWSE_UNFILTERED] = user_input[CONF_BROWSE_UNFILTERED]

            # Save if there's no errors, else fall through and show the form again
            if not errors:
                return self.async_create_entry(title="", data=options)

        fields = {}

        def _add_with_suggestion(key: str, validator: Callable | type[bool]) -> None:
            """Add a field to with a suggested value.

            For bools, use the existing value as default, or fallback to False.
            """
            if validator is bool:
                fields[vol.Required(key, default=options.get(key, False))] = validator
            elif (suggested_value := options.get(key)) is None:
                fields[vol.Optional(key)] = validator
            else:
                fields[
                    vol.Optional(key, description={"suggested_value": suggested_value})
                ] = validator

        # listen_port can be blank or 0 for "bind any free port"
        _add_with_suggestion(CONF_LISTEN_PORT, cv.port)
        _add_with_suggestion(CONF_CALLBACK_URL_OVERRIDE, str)
        _add_with_suggestion(CONF_POLL_AVAILABILITY, bool)
        _add_with_suggestion(CONF_BROWSE_UNFILTERED, bool)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors=errors,
        )


def _is_ignored_device(discovery_info: ssdp.SsdpServiceInfo) -> bool:
    """Return True if this device should be ignored for discovery.

    These devices are supported better by other integrations, so don't bug
    the user about them. The user can add them if desired by via the user config
    flow, which will list all discovered but unconfigured devices.
    """
    # Did the discovery trigger more than just this flow?
    if len(discovery_info.x_homeassistant_matching_domains) > 1:
        LOGGER.debug(
            "Ignoring device supported by multiple integrations: %s",
            discovery_info.x_homeassistant_matching_domains,
        )
        return True

    # Is the root device not a DMR?
    if (
        discovery_info.upnp.get(ssdp.ATTR_UPNP_DEVICE_TYPE)
        not in DmrDevice.DEVICE_TYPES
    ):
        return True

    # Special cases for devices with other discovery methods (e.g. mDNS), or
    # that advertise multiple unrelated (sent in separate discovery packets)
    # UPnP devices.
    manufacturer = (discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER) or "").lower()
    model = (discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME) or "").lower()

    if manufacturer.startswith("xbmc") or model == "kodi":
        # kodi
        return True
    if "philips" in manufacturer and "tv" in model:
        # philips_js
        # These TVs don't have a stable UDN, so also get discovered as a new
        # device every time they are turned on.
        return True
    if manufacturer.startswith("samsung") and "tv" in model:
        # samsungtv
        return True
    if manufacturer.startswith("lg") and "tv" in model:
        # webostv
        return True

    return False


def _is_dmr_device(discovery_info: ssdp.SsdpServiceInfo) -> bool:
    """Determine if discovery is a complete DLNA DMR device.

    Use the discovery_info instead of DmrDevice.is_profile_device to avoid
    contacting the device again.
    """
    # Abort if the device doesn't support all services required for a DmrDevice.
    discovery_service_list = discovery_info.upnp.get(ssdp.ATTR_UPNP_SERVICE_LIST)
    if not discovery_service_list:
        return False

    services = discovery_service_list.get("service")
    if not services:
        discovery_service_ids: set[str] = set()
    elif isinstance(services, list):
        discovery_service_ids = {service.get("serviceId") for service in services}
    else:
        # Only one service defined (etree_to_dict failed to make a list)
        discovery_service_ids = {services.get("serviceId")}

    if not DmrDevice.SERVICE_IDS.issubset(discovery_service_ids):
        return False

    return True


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
