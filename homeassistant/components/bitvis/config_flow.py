"""Config flow for the Bitvis Power Hub integration."""

import asyncio
import logging
from typing import Any, Self, override

from bitvis_protobuf.listener import FilterIp
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
from bitvis_protobuf.utils import (
    InvalidMacAddressError,
    async_resolve_host,
    async_verify_udp_port_bindable,
    normalize_host,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_NAME, DEFAULT_PORT, DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import async_get_listener_registry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


async def _async_test_port(hass: HomeAssistant, port: int) -> None:
    """Verify the UDP port can be bound."""

    if async_get_listener_registry(hass).has_listener(port):
        return

    await async_verify_udp_port_bindable(port)


async def _async_discover_mac_address(hass: HomeAssistant, host: str, port: int) -> str:
    """Wait for a UDP message from the device and return its MAC address."""
    resolved_ips = await async_resolve_host(host)
    listener_registry = async_get_listener_registry(hass)
    listener = await listener_registry.async_get_or_create(port)

    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    @callback
    def _on_payload(
        payload: PayloadSample | PayloadDiagnostic, _addr: tuple[str, int]
    ) -> None:
        if not future.done():
            future.set_result(payload.mac_address)

    filters: list[FilterIp] = []
    original_dispatch = listener.dispatch

    def dispatch(data: bytes, addr: tuple[str, int]) -> None:
        try:
            original_dispatch(data, addr)
        except InvalidMacAddressError as err:
            if not future.done():
                future.set_exception(err)

    listener.dispatch = dispatch  # type: ignore[method-assign]
    try:
        for ip in resolved_ips:
            filt = FilterIp(ip)
            try:
                listener.register(filt, _on_payload)
            except RuntimeError as err:
                raise AbortFlow("already_in_progress") from err
            filters.append(filt)

        return await asyncio.wait_for(future, timeout=DISCOVERY_TIMEOUT)
    finally:
        listener.dispatch = original_dispatch  # type: ignore[method-assign]
        for filt in filters:
            listener.unregister(filt)
        await listener_registry.async_remove_if_unused(port)


class BitvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitvis Power Hub."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: ZeroconfServiceInfo | None = None
        self._validated_host: str | None = None
        self._host: str | None = None

    @override
    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return (
            self._host is not None
            and other_flow._host is not None
            and normalize_host(self._host) == normalize_host(other_flow._host)
        )

    def _get_friendly_name(self, name: str | None) -> str:
        """Return a user-friendly name derived from the zeroconf name."""
        if not name:
            return DEFAULT_NAME
        instance = name.split(".", 1)[0]
        return instance or DEFAULT_NAME

    async def _async_validate_host(self, host: str) -> str:
        """Verify port availability and discover the device MAC address."""
        await _async_test_port(self.hass, DEFAULT_PORT)
        return await _async_discover_mac_address(self.hass, host, DEFAULT_PORT)

    async def _async_create_entry_from_host(
        self, host: str, title: str
    ) -> ConfigFlowResult:
        """Validate connectivity, discover MAC address, and create the entry."""
        self._host = host
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        try:
            mac_address = await self._async_validate_host(host)
        except TimeoutError:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, {CONF_HOST: host}
                ),
                errors={"base": "timeout_connect"},
            )
        except InvalidMacAddressError:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, {CONF_HOST: host}
                ),
                errors={"base": "invalid_mac"},
            )
        except OSError:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, {CONF_HOST: host}
                ),
                errors={"base": "cannot_connect"},
            )

        await self.async_set_unique_id(format_mac(mac_address))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: host,
                CONF_PORT: DEFAULT_PORT,
            },
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            self._async_abort_entries_match({CONF_HOST: host})
            return await self._async_create_entry_from_host(host, DEFAULT_NAME)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered Bitvis Power Hub via Zeroconf: %s", discovery_info)

        host = discovery_info.host
        self._host = host

        self._async_abort_entries_match({CONF_HOST: host})

        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        try:
            mac_address = await self._async_validate_host(host)
        except TimeoutError:
            return self.async_abort(reason="timeout_connect")
        except InvalidMacAddressError:
            return self.async_abort(reason="invalid_mac")
        except OSError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(format_mac(mac_address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._validated_host = host

        self.context["title_placeholders"] = {
            "name": self._get_friendly_name(discovery_info.name),
            "host": host,
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            assert self._discovery_info is not None
            assert self._validated_host is not None

            return self.async_create_entry(
                title=self._get_friendly_name(self._discovery_info.name),
                data={
                    CONF_HOST: self._validated_host,
                    CONF_PORT: DEFAULT_PORT,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._get_friendly_name(
                    self._discovery_info.name if self._discovery_info else None
                ),
                "host": self._discovery_info.host if self._discovery_info else "",
            },
        )
