"""Config flow for Samsung TV."""
from __future__ import annotations

from functools import partial
import socket
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

import getmac
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import DiscoveryInfoType

from .bridge import (
    SamsungTVBridge,
    SamsungTVLegacyBridge,
    SamsungTVWSBridge,
    async_get_device_info,
    mac_from_device_info,
)
from .const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    DEFAULT_MANUFACTURER,
    DOMAIN,
    LEGACY_PORT,
    LOGGER,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    RESULT_UNKNOWN_HOST,
    WEBSOCKET_PORTS,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})
SUPPORTED_METHODS = [METHOD_LEGACY, METHOD_WEBSOCKET]


def _strip_uuid(udn: str) -> str:
    return udn[5:] if udn.startswith("uuid:") else udn


def _entry_is_complete(entry: config_entries.ConfigEntry) -> bool:
    """Return True if the config entry information is complete."""
    return bool(entry.unique_id and entry.data.get(CONF_MAC))


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._host: str = ""
        self._mac: str | None = None
        self._udn: str | None = None
        self._manufacturer: str | None = None
        self._model: str | None = None
        self._name: str | None = None
        self._title: str = ""
        self._id: int | None = None
        self._bridge: SamsungTVLegacyBridge | SamsungTVWSBridge | None = None
        self._device_info: dict[str, Any] | None = None

    def _get_entry_from_bridge(self) -> data_entry_flow.FlowResult:
        """Get device entry."""
        assert self._bridge

        data = {
            CONF_HOST: self._host,
            CONF_MAC: self._mac,
            CONF_MANUFACTURER: self._manufacturer or DEFAULT_MANUFACTURER,
            CONF_METHOD: self._bridge.method,
            CONF_MODEL: self._model,
            CONF_NAME: self._name,
            CONF_PORT: self._bridge.port,
        }
        if self._bridge.token:
            data[CONF_TOKEN] = self._bridge.token
        return self.async_create_entry(
            title=self._title,
            data=data,
        )

    async def _async_set_device_unique_id(self, raise_on_progress: bool = True) -> None:
        """Set device unique_id."""
        if not await self._async_get_and_check_device_info():
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
        await self._async_set_unique_id_from_udn(raise_on_progress)
        self._async_update_and_abort_for_matching_unique_id()

    async def _async_set_unique_id_from_udn(
        self, raise_on_progress: bool = True
    ) -> None:
        """Set the unique id from the udn."""
        assert self._host is not None
        await self.async_set_unique_id(self._udn, raise_on_progress=raise_on_progress)
        if (entry := self._async_update_existing_host_entry()) and _entry_is_complete(
            entry
        ):
            raise data_entry_flow.AbortFlow("already_configured")

    def _async_update_and_abort_for_matching_unique_id(self) -> None:
        """Abort and update host and mac if we have it."""
        updates = {CONF_HOST: self._host}
        if self._mac:
            updates[CONF_MAC] = self._mac
        self._abort_if_unique_id_configured(updates=updates)

    def _try_connect(self) -> None:
        """Try to connect and check auth."""
        for method in SUPPORTED_METHODS:
            self._bridge = SamsungTVBridge.get_bridge(method, self._host)
            result = self._bridge.try_connect()
            if result == RESULT_SUCCESS:
                return
            if result != RESULT_CANNOT_CONNECT:
                raise data_entry_flow.AbortFlow(result)
        LOGGER.debug("No working config found")
        raise data_entry_flow.AbortFlow(RESULT_CANNOT_CONNECT)

    async def _async_get_and_check_device_info(self) -> bool:
        """Try to get the device info."""
        _port, _method, info = await async_get_device_info(
            self.hass, self._bridge, self._host
        )
        if not info:
            if not _method:
                LOGGER.debug(
                    "Samsung host %s is not supported by either %s or %s methods",
                    self._host,
                    METHOD_LEGACY,
                    METHOD_WEBSOCKET,
                )
                raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
            return False
        dev_info = info.get("device", {})
        if (device_type := dev_info.get("type")) != "Samsung SmartTV":
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
        self._model = dev_info.get("modelName")
        name = dev_info.get("name")
        self._name = name.replace("[TV] ", "") if name else device_type
        self._title = f"{self._name} ({self._model})"
        self._udn = _strip_uuid(dev_info.get("udn", info["id"]))
        if mac := mac_from_device_info(info):
            self._mac = mac
        elif mac := await self.hass.async_add_executor_job(
            partial(getmac.get_mac_address, ip=self._host)
        ):
            self._mac = mac
        self._device_info = info
        return True

    async def async_step_import(
        self, user_input: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Handle configuration by yaml file."""
        # We need to import even if we cannot validate
        # since the TV may be off at startup
        await self._async_set_name_host_from_input(user_input)
        self._async_abort_entries_match({CONF_HOST: self._host})
        port = user_input.get(CONF_PORT)
        if port in WEBSOCKET_PORTS:
            user_input[CONF_METHOD] = METHOD_WEBSOCKET
        elif port == LEGACY_PORT:
            user_input[CONF_METHOD] = METHOD_LEGACY
        user_input[CONF_MANUFACTURER] = DEFAULT_MANUFACTURER
        return self.async_create_entry(
            title=self._title,
            data=user_input,
        )

    async def _async_set_name_host_from_input(self, user_input: dict[str, Any]) -> None:
        try:
            self._host = await self.hass.async_add_executor_job(
                socket.gethostbyname, user_input[CONF_HOST]
            )
        except socket.gaierror as err:
            raise data_entry_flow.AbortFlow(RESULT_UNKNOWN_HOST) from err
        self._name = user_input.get(CONF_NAME, self._host) or ""
        self._title = self._name

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            await self._async_set_name_host_from_input(user_input)
            await self.hass.async_add_executor_job(self._try_connect)
            assert self._bridge
            self._async_abort_entries_match({CONF_HOST: self._host})
            if self._bridge.method != METHOD_LEGACY:
                # Legacy bridge does not provide device info
                await self._async_set_device_unique_id(raise_on_progress=False)
            return self._get_entry_from_bridge()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    @callback
    def _async_update_existing_host_entry(self) -> config_entries.ConfigEntry | None:
        """Check existing entries and update them.

        Returns the existing entry if it was updated.
        """
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] != self._host:
                continue
            entry_kw_args: dict = {}
            if self.unique_id and entry.unique_id is None:
                entry_kw_args["unique_id"] = self.unique_id
            if self._mac and not entry.data.get(CONF_MAC):
                entry_kw_args["data"] = {**entry.data, CONF_MAC: self._mac}
            if entry_kw_args:
                self.hass.config_entries.async_update_entry(entry, **entry_kw_args)
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return entry
        return None

    async def _async_start_discovery_with_mac_address(self) -> None:
        """Start discovery."""
        assert self._host is not None
        if (entry := self._async_update_existing_host_entry()) and entry.unique_id:
            # If we have the unique id and the mac we abort
            # as we do not need anything else
            raise data_entry_flow.AbortFlow("already_configured")
        self._async_abort_if_host_already_in_progress()

    @callback
    def _async_abort_if_host_already_in_progress(self) -> None:
        self.context[CONF_HOST] = self._host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._host:
                raise data_entry_flow.AbortFlow("already_in_progress")

    @callback
    def _abort_if_manufacturer_is_not_samsung(self) -> None:
        if not self._manufacturer or not self._manufacturer.lower().startswith(
            "samsung"
        ):
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)

    async def async_step_ssdp(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by ssdp discovery."""
        LOGGER.debug("Samsung device found via SSDP: %s", discovery_info)
        model_name: str = discovery_info.get(ATTR_UPNP_MODEL_NAME) or ""
        self._udn = _strip_uuid(discovery_info[ATTR_UPNP_UDN])
        if hostname := urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname:
            self._host = hostname
        await self._async_set_unique_id_from_udn()
        self._manufacturer = discovery_info[ATTR_UPNP_MANUFACTURER]
        self._abort_if_manufacturer_is_not_samsung()
        if not await self._async_get_and_check_device_info():
            # If we cannot get device info for an SSDP discovery
            # its likely a legacy tv.
            self._name = self._title = self._model = model_name
        self._async_update_and_abort_for_matching_unique_id()
        self._async_abort_if_host_already_in_progress()
        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by dhcp discovery."""
        LOGGER.debug("Samsung device found via DHCP: %s", discovery_info)
        self._mac = discovery_info[dhcp.MAC_ADDRESS]
        self._host = discovery_info[dhcp.IP_ADDRESS]
        await self._async_start_discovery_with_mac_address()
        await self._async_set_device_unique_id()
        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        LOGGER.debug("Samsung device found via ZEROCONF: %s", discovery_info)
        self._mac = format_mac(discovery_info[zeroconf.ATTR_PROPERTIES]["deviceid"])
        self._host = discovery_info[zeroconf.ATTR_HOST]
        await self._async_start_discovery_with_mac_address()
        await self._async_set_device_unique_id()
        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:

            await self.hass.async_add_executor_job(self._try_connect)
            assert self._bridge
            return self._get_entry_from_bridge()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"device": self._title}
        )

    async def async_step_reauth(
        self, data: MappingProxyType[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert self._reauth_entry
        data = self._reauth_entry.data
        if data.get(CONF_MODEL) and data.get(CONF_NAME):
            self._title = f"{data[CONF_NAME]} ({data[CONF_MODEL]})"
        else:
            self._title = data.get(CONF_NAME) or data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Confirm reauth."""
        errors = {}
        assert self._reauth_entry
        if user_input is not None:
            bridge = SamsungTVBridge.get_bridge(
                self._reauth_entry.data[CONF_METHOD], self._reauth_entry.data[CONF_HOST]
            )
            result = await self.hass.async_add_executor_job(bridge.try_connect)
            if result == RESULT_SUCCESS:
                new_data = dict(self._reauth_entry.data)
                new_data[CONF_TOKEN] = bridge.token
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            if result not in (RESULT_AUTH_MISSING, RESULT_CANNOT_CONNECT):
                return self.async_abort(reason=result)

            # On websocket we will get RESULT_CANNOT_CONNECT when auth is missing
            errors = {"base": RESULT_AUTH_MISSING}

        self.context["title_placeholders"] = {"device": self._title}
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            description_placeholders={"device": self._title},
        )
