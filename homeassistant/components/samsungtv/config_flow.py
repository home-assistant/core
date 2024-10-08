"""Config flow for Samsung TV."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import socket
from typing import Any, Self
from urllib.parse import urlparse

import getmac
from samsungtvws.encrypted.authenticator import SamsungTVEncryptedWSAsyncAuthenticator
import voluptuous as vol

from homeassistant.components import dhcp, ssdp, zeroconf
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .bridge import SamsungTVBridge, async_get_device_info, mac_from_device_info
from .const import (
    CONF_MANUFACTURER,
    CONF_SESSION_ID,
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    DEFAULT_MANUFACTURER,
    DOMAIN,
    LOGGER,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_INVALID_PIN,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    RESULT_UNKNOWN_HOST,
    SUCCESSFUL_RESULTS,
    UPNP_SVC_MAIN_TV_AGENT,
    UPNP_SVC_RENDERING_CONTROL,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})


def _strip_uuid(udn: str) -> str:
    return udn[5:] if udn.startswith("uuid:") else udn


def _entry_is_complete(
    entry: ConfigEntry,
    ssdp_rendering_control_location: str | None,
    ssdp_main_tv_agent_location: str | None,
) -> bool:
    """Return True if the config entry information is complete.

    If we do not have an ssdp location we consider it complete
    as some TVs will not support SSDP/UPNP
    """
    return bool(
        entry.unique_id
        and entry.data.get(CONF_MAC)
        and (
            not ssdp_rendering_control_location
            or entry.data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION)
        )
        and (
            not ssdp_main_tv_agent_location
            or entry.data.get(CONF_SSDP_MAIN_TV_AGENT_LOCATION)
        )
    )


def _mac_is_same_with_incorrect_formatting(
    current_unformatted_mac: str, formatted_mac: str
) -> bool:
    """Check if two macs are the same but formatted incorrectly."""
    current_formatted_mac = format_mac(current_unformatted_mac)
    return (
        current_formatted_mac == formatted_mac
        and current_unformatted_mac != current_formatted_mac
    )


class SamsungTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._reauth_entry: ConfigEntry | None = None
        self._host: str = ""
        self._mac: str | None = None
        self._udn: str | None = None
        self._upnp_udn: str | None = None
        self._ssdp_rendering_control_location: str | None = None
        self._ssdp_main_tv_agent_location: str | None = None
        self._manufacturer: str | None = None
        self._model: str | None = None
        self._connect_result: str | None = None
        self._method: str | None = None
        self._name: str | None = None
        self._title: str = ""
        self._id: int | None = None
        self._bridge: SamsungTVBridge | None = None
        self._device_info: dict[str, Any] | None = None
        self._authenticator: SamsungTVEncryptedWSAsyncAuthenticator | None = None

    def _base_config_entry(self) -> dict[str, Any]:
        """Generate the base config entry without the method."""
        assert self._bridge is not None
        return {
            CONF_HOST: self._host,
            CONF_MAC: self._mac,
            CONF_MANUFACTURER: self._manufacturer or DEFAULT_MANUFACTURER,
            CONF_METHOD: self._bridge.method,
            CONF_MODEL: self._model,
            CONF_NAME: self._name,
            CONF_PORT: self._bridge.port,
            CONF_SSDP_RENDERING_CONTROL_LOCATION: self._ssdp_rendering_control_location,
            CONF_SSDP_MAIN_TV_AGENT_LOCATION: self._ssdp_main_tv_agent_location,
        }

    def _get_entry_from_bridge(self) -> ConfigFlowResult:
        """Get device entry."""
        assert self._bridge
        data = self._base_config_entry()
        if self._bridge.token:
            data[CONF_TOKEN] = self._bridge.token
        return self.async_create_entry(
            title=self._title,
            data=data,
        )

    async def _async_set_device_unique_id(self, raise_on_progress: bool = True) -> None:
        """Set device unique_id."""
        if not await self._async_get_and_check_device_info():
            raise AbortFlow(RESULT_NOT_SUPPORTED)
        await self._async_set_unique_id_from_udn(raise_on_progress)
        self._async_update_and_abort_for_matching_unique_id()

    async def _async_set_unique_id_from_udn(
        self, raise_on_progress: bool = True
    ) -> None:
        """Set the unique id from the udn."""
        assert self._host is not None
        # Set the unique id without raising on progress in case
        # there are two SSDP flows with for each ST
        await self.async_set_unique_id(self._udn, raise_on_progress=False)
        if (
            entry := self._async_update_existing_matching_entry()
        ) and _entry_is_complete(
            entry,
            self._ssdp_rendering_control_location,
            self._ssdp_main_tv_agent_location,
        ):
            raise AbortFlow("already_configured")
        # Now that we have updated the config entry, we can raise
        # if another one is progressing
        if raise_on_progress:
            await self.async_set_unique_id(self._udn, raise_on_progress=True)

    def _async_update_and_abort_for_matching_unique_id(self) -> None:
        """Abort and update host and mac if we have it."""
        updates = {CONF_HOST: self._host}
        if self._mac:
            updates[CONF_MAC] = self._mac
        if self._model:
            updates[CONF_MODEL] = self._model
        if self._ssdp_rendering_control_location:
            updates[CONF_SSDP_RENDERING_CONTROL_LOCATION] = (
                self._ssdp_rendering_control_location
            )
        if self._ssdp_main_tv_agent_location:
            updates[CONF_SSDP_MAIN_TV_AGENT_LOCATION] = (
                self._ssdp_main_tv_agent_location
            )
        self._abort_if_unique_id_configured(updates=updates, reload_on_update=False)

    async def _async_create_bridge(self) -> None:
        """Create the bridge."""
        result, method, _info = await self._async_get_device_info_and_method()
        if result not in SUCCESSFUL_RESULTS:
            LOGGER.debug("No working config found for %s", self._host)
            raise AbortFlow(result)
        assert method is not None
        self._bridge = SamsungTVBridge.get_bridge(self.hass, method, self._host)

    async def _async_get_device_info_and_method(
        self,
    ) -> tuple[str, str | None, dict[str, Any] | None]:
        """Get device info and method only once."""
        if self._connect_result is None:
            result, _, method, info = await async_get_device_info(self.hass, self._host)
            self._connect_result = result
            self._method = method
            self._device_info = info
            if not method:
                LOGGER.debug("Host:%s did not return device info", self._host)
                return result, None, None
        return self._connect_result, self._method, self._device_info

    async def _async_get_and_check_device_info(self) -> bool:
        """Try to get the device info."""
        result, _method, info = await self._async_get_device_info_and_method()
        if result not in SUCCESSFUL_RESULTS:
            raise AbortFlow(result)
        if not info:
            return False
        dev_info = info.get("device", {})
        assert dev_info is not None
        if (device_type := dev_info.get("type")) != "Samsung SmartTV":
            LOGGER.debug(
                "Host:%s has type: %s which is not supported", self._host, device_type
            )
            raise AbortFlow(RESULT_NOT_SUPPORTED)
        self._model = dev_info.get("modelName")
        name = dev_info.get("name")
        self._name = name.replace("[TV] ", "") if name else device_type
        self._title = f"{self._name} ({self._model})"
        self._udn = _strip_uuid(dev_info.get("udn", info["id"]))
        if mac := mac_from_device_info(info):
            # Samsung sometimes returns a value of "none" for the mac address
            # this should be ignored - but also shouldn't trigger getmac
            if mac != "none":
                self._mac = mac
        elif mac := await self.hass.async_add_executor_job(
            partial(getmac.get_mac_address, ip=self._host)
        ):
            self._mac = mac
        return True

    async def _async_set_name_host_from_input(self, user_input: dict[str, Any]) -> None:
        try:
            self._host = await self.hass.async_add_executor_job(
                socket.gethostbyname, user_input[CONF_HOST]
            )
        except socket.gaierror as err:
            raise AbortFlow(RESULT_UNKNOWN_HOST) from err
        self._name = user_input.get(CONF_NAME, self._host) or ""
        self._title = self._name

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            await self._async_set_name_host_from_input(user_input)
            await self._async_create_bridge()
            assert self._bridge
            self._async_abort_entries_match({CONF_HOST: self._host})
            if self._bridge.method != METHOD_LEGACY:
                # Legacy bridge does not provide device info
                await self._async_set_device_unique_id(raise_on_progress=False)
            if self._bridge.method == METHOD_ENCRYPTED_WEBSOCKET:
                return await self.async_step_encrypted_pairing()
            return await self.async_step_pairing({})

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a pairing by accepting the message on the TV."""
        assert self._bridge is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._bridge.async_try_connect()
            if result == RESULT_SUCCESS:
                return self._get_entry_from_bridge()
            if result != RESULT_AUTH_MISSING:
                raise AbortFlow(result)
            errors = {"base": RESULT_AUTH_MISSING}

        self.context["title_placeholders"] = {"device": self._title}
        return self.async_show_form(
            step_id="pairing",
            errors=errors,
            description_placeholders={"device": self._title},
            data_schema=vol.Schema({}),
        )

    async def async_step_encrypted_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a encrypted pairing."""
        assert self._host is not None
        await self._async_start_encrypted_pairing(self._host)
        assert self._authenticator is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            if (
                (pin := user_input.get("pin"))
                and (token := await self._authenticator.try_pin(pin))
                and (session_id := await self._authenticator.get_session_id_and_close())
            ):
                return self.async_create_entry(
                    data={
                        **self._base_config_entry(),
                        CONF_TOKEN: token,
                        CONF_SESSION_ID: session_id,
                    },
                    title=self._title,
                )
            errors = {"base": RESULT_INVALID_PIN}

        self.context["title_placeholders"] = {"device": self._title}
        return self.async_show_form(
            step_id="encrypted_pairing",
            errors=errors,
            description_placeholders={"device": self._title},
            data_schema=vol.Schema({vol.Required("pin"): str}),
        )

    @callback
    def _async_get_existing_matching_entry(
        self,
    ) -> tuple[ConfigEntry | None, bool]:
        """Get first existing matching entry (prefer unique id)."""
        matching_host_entry: ConfigEntry | None = None
        for entry in self._async_current_entries(include_ignore=False):
            if (self._mac and self._mac == entry.data.get(CONF_MAC)) or (
                self._upnp_udn and self._upnp_udn == entry.unique_id
            ):
                LOGGER.debug("Found entry matching unique_id for %s", self._host)
                return entry, True

            if entry.data[CONF_HOST] == self._host:
                LOGGER.debug("Found entry matching host for %s", self._host)
                matching_host_entry = entry

        return matching_host_entry, False

    @callback
    def _async_update_existing_matching_entry(
        self,
    ) -> ConfigEntry | None:
        """Check existing entries and update them.

        Returns the existing entry if it was updated.
        """
        entry, is_unique_match = self._async_get_existing_matching_entry()
        if not entry:
            return None
        entry_kw_args: dict = {}
        if self.unique_id and (
            entry.unique_id is None
            or (is_unique_match and self.unique_id != entry.unique_id)
        ):
            entry_kw_args["unique_id"] = self.unique_id
        data: dict[str, Any] = dict(entry.data)
        update_ssdp_rendering_control_location = (
            self._ssdp_rendering_control_location
            and data.get(CONF_SSDP_RENDERING_CONTROL_LOCATION)
            != self._ssdp_rendering_control_location
        )
        update_ssdp_main_tv_agent_location = (
            self._ssdp_main_tv_agent_location
            and data.get(CONF_SSDP_MAIN_TV_AGENT_LOCATION)
            != self._ssdp_main_tv_agent_location
        )
        update_mac = self._mac and (
            not (data_mac := data.get(CONF_MAC))
            or _mac_is_same_with_incorrect_formatting(data_mac, self._mac)
        )
        update_model = self._model and not data.get(CONF_MODEL)
        if (
            update_ssdp_rendering_control_location
            or update_ssdp_main_tv_agent_location
            or update_mac
            or update_model
        ):
            if update_ssdp_rendering_control_location:
                data[CONF_SSDP_RENDERING_CONTROL_LOCATION] = (
                    self._ssdp_rendering_control_location
                )
            if update_ssdp_main_tv_agent_location:
                data[CONF_SSDP_MAIN_TV_AGENT_LOCATION] = (
                    self._ssdp_main_tv_agent_location
                )
            if update_mac:
                data[CONF_MAC] = self._mac
            if update_model:
                data[CONF_MODEL] = self._model
            entry_kw_args["data"] = data
        if not entry_kw_args:
            return None
        LOGGER.debug("Updating existing config entry with %s", entry_kw_args)
        self.hass.config_entries.async_update_entry(entry, **entry_kw_args)
        if entry.state != ConfigEntryState.LOADED:
            # If its loaded it already has a reload listener in place
            # and we do not want to trigger multiple reloads
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )
        return entry

    @callback
    def _async_start_discovery_with_mac_address(self) -> None:
        """Start discovery."""
        assert self._host is not None
        if (entry := self._async_update_existing_matching_entry()) and entry.unique_id:
            # If we have the unique id and the mac we abort
            # as we do not need anything else
            raise AbortFlow("already_configured")
        self._async_abort_if_host_already_in_progress()

    @callback
    def _async_abort_if_host_already_in_progress(self) -> None:
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            raise AbortFlow("already_in_progress")

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return other_flow._host == self._host  # noqa: SLF001

    @callback
    def _abort_if_manufacturer_is_not_samsung(self) -> None:
        if not self._manufacturer or not self._manufacturer.lower().startswith(
            "samsung"
        ):
            raise AbortFlow(RESULT_NOT_SUPPORTED)

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by ssdp discovery."""
        LOGGER.debug("Samsung device found via SSDP: %s", discovery_info)
        model_name: str = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME) or ""
        if discovery_info.ssdp_st == UPNP_SVC_RENDERING_CONTROL:
            self._ssdp_rendering_control_location = discovery_info.ssdp_location
            LOGGER.debug(
                "Set SSDP RenderingControl location to: %s",
                self._ssdp_rendering_control_location,
            )
        elif discovery_info.ssdp_st == UPNP_SVC_MAIN_TV_AGENT:
            self._ssdp_main_tv_agent_location = discovery_info.ssdp_location
            LOGGER.debug(
                "Set SSDP MainTvAgent location to: %s",
                self._ssdp_main_tv_agent_location,
            )
        self._udn = self._upnp_udn = _strip_uuid(
            discovery_info.upnp[ssdp.ATTR_UPNP_UDN]
        )
        if hostname := urlparse(discovery_info.ssdp_location or "").hostname:
            self._host = hostname
        self._manufacturer = discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER)
        self._abort_if_manufacturer_is_not_samsung()

        # Set defaults, in case they cannot be extracted from device_info
        self._name = self._title = self._model = model_name
        # Update from device_info (if accessible)
        await self._async_get_and_check_device_info()

        # The UDN provided by the ssdp discovery doesn't always match the UDN
        # from the device_info, used by the other methods so we need to
        # ensure the device_info is loaded before setting the unique_id
        await self._async_set_unique_id_from_udn()
        self._async_update_and_abort_for_matching_unique_id()
        self._async_abort_if_host_already_in_progress()
        if self._method == METHOD_LEGACY and discovery_info.ssdp_st in (
            UPNP_SVC_RENDERING_CONTROL,
            UPNP_SVC_MAIN_TV_AGENT,
        ):
            # The UDN we use for the unique id cannot be determined
            # from device_info for legacy devices
            return self.async_abort(reason="not_supported")
        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by dhcp discovery."""
        LOGGER.debug("Samsung device found via DHCP: %s", discovery_info)
        self._mac = format_mac(discovery_info.macaddress)
        self._host = discovery_info.ip
        self._async_start_discovery_with_mac_address()
        await self._async_set_device_unique_id()
        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        LOGGER.debug("Samsung device found via ZEROCONF: %s", discovery_info)
        self._mac = format_mac(discovery_info.properties["deviceid"])
        self._host = discovery_info.host
        self._async_start_discovery_with_mac_address()
        await self._async_set_device_unique_id()
        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            await self._async_create_bridge()
            assert self._bridge
            if self._bridge.method == METHOD_ENCRYPTED_WEBSOCKET:
                return await self.async_step_encrypted_pairing()
            return await self.async_step_pairing({})

        return self.async_show_form(
            step_id="confirm", description_placeholders={"device": self._title}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if entry_data.get(CONF_MODEL) and entry_data.get(CONF_NAME):
            self._title = f"{entry_data[CONF_NAME]} ({entry_data[CONF_MODEL]})"
        else:
            self._title = entry_data.get(CONF_NAME) or entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth."""
        errors = {}
        assert self._reauth_entry
        method = self._reauth_entry.data[CONF_METHOD]
        if user_input is not None:
            if method == METHOD_ENCRYPTED_WEBSOCKET:
                return await self.async_step_reauth_confirm_encrypted()
            bridge = SamsungTVBridge.get_bridge(
                self.hass,
                method,
                self._reauth_entry.data[CONF_HOST],
            )
            result = await bridge.async_try_connect()
            if result == RESULT_SUCCESS:
                new_data = dict(self._reauth_entry.data)
                new_data[CONF_TOKEN] = bridge.token
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data=new_data,
                )
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

    async def _async_start_encrypted_pairing(self, host: str) -> None:
        if self._authenticator is None:
            self._authenticator = SamsungTVEncryptedWSAsyncAuthenticator(
                host,
                web_session=async_get_clientsession(self.hass),
            )
            await self._authenticator.start_pairing()

    async def async_step_reauth_confirm_encrypted(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth (encrypted method)."""
        errors = {}
        assert self._reauth_entry
        await self._async_start_encrypted_pairing(self._reauth_entry.data[CONF_HOST])
        assert self._authenticator is not None

        if user_input is not None:
            if (
                (pin := user_input.get("pin"))
                and (token := await self._authenticator.try_pin(pin))
                and (session_id := await self._authenticator.get_session_id_and_close())
            ):
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_TOKEN: token,
                        CONF_SESSION_ID: session_id,
                    },
                )

            errors = {"base": RESULT_INVALID_PIN}

        self.context["title_placeholders"] = {"device": self._title}
        return self.async_show_form(
            step_id="reauth_confirm_encrypted",
            errors=errors,
            description_placeholders={"device": self._title},
            data_schema=vol.Schema({vol.Required("pin"): str}),
        )
