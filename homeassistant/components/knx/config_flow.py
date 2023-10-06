"""Config flow for KNX."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, Final

import voluptuous as vol
from xknx import XKNX
from xknx.exceptions.exception import (
    CommunicationError,
    InvalidSecureConfiguration,
    XKNXException,
)
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.io.gateway_scanner import GatewayDescriptor, GatewayScanner
from xknx.io.self_description import request_description
from xknx.io.util import validate_ip as xknx_validate_ip
from xknx.secure.keyring import Keyring, XMLInterface

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.typing import UNDEFINED

from .const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_ROUTING_SECURE,
    CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_ID,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TELEGRAM_LOG_SIZE,
    CONF_KNX_TUNNEL_ENDPOINT_IA,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    DEFAULT_ROUTING_IA,
    DOMAIN,
    TELEGRAM_LOG_DEFAULT,
    TELEGRAM_LOG_MAX,
    KNXConfigEntryData,
)
from .helpers.keyring import DEFAULT_KNX_KEYRING_FILENAME, save_uploaded_knxkeys_file
from .schema import ia_validator, ip_v4_validator

CONF_KNX_GATEWAY: Final = "gateway"
CONF_MAX_RATE_LIMIT: Final = 60

DEFAULT_ENTRY_DATA = KNXConfigEntryData(
    individual_address=DEFAULT_ROUTING_IA,
    local_ip=None,
    multicast_group=DEFAULT_MCAST_GRP,
    multicast_port=DEFAULT_MCAST_PORT,
    rate_limit=CONF_KNX_DEFAULT_RATE_LIMIT,
    route_back=False,
    state_updater=CONF_KNX_DEFAULT_STATE_UPDATER,
    telegram_log_size=TELEGRAM_LOG_DEFAULT,
)

CONF_KEYRING_FILE: Final = "knxkeys_file"

CONF_KNX_TUNNELING_TYPE: Final = "tunneling_type"
CONF_KNX_TUNNELING_TYPE_LABELS: Final = {
    CONF_KNX_TUNNELING: "UDP (Tunnelling v1)",
    CONF_KNX_TUNNELING_TCP: "TCP (Tunnelling v2)",
    CONF_KNX_TUNNELING_TCP_SECURE: "Secure Tunnelling (TCP)",
}

OPTION_MANUAL_TUNNEL: Final = "Manual"

_IA_SELECTOR = selector.TextSelector()
_IP_SELECTOR = selector.TextSelector()
_PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
        ),
    ),
    vol.Coerce(int),
)


class KNXCommonFlow(ABC, FlowHandler):
    """Base class for KNX flows."""

    def __init__(self, initial_data: KNXConfigEntryData) -> None:
        """Initialize KNXCommonFlow."""
        self.initial_data = initial_data
        self.new_entry_data = KNXConfigEntryData()
        self.new_title: str | None = None

        self._keyring: Keyring | None = None
        self._found_gateways: list[GatewayDescriptor] = []
        self._found_tunnels: list[GatewayDescriptor] = []
        self._selected_tunnel: GatewayDescriptor | None = None
        self._tunnel_endpoints: list[XMLInterface] = []

        self._gatewayscanner: GatewayScanner | None = None
        self._async_scan_gen: AsyncGenerator[GatewayDescriptor, None] | None = None

    @abstractmethod
    def finish_flow(self) -> FlowResult:
        """Finish the flow."""

    @property
    def connection_type(self) -> str:
        """Return the configured connection type."""
        _new_type = self.new_entry_data.get(CONF_KNX_CONNECTION_TYPE)
        if _new_type is None:
            return self.initial_data[CONF_KNX_CONNECTION_TYPE]
        return _new_type

    @property
    def tunnel_endpoint_ia(self) -> str | None:
        """Return the configured tunnel endpoint individual address."""
        return self.new_entry_data.get(
            CONF_KNX_TUNNEL_ENDPOINT_IA,
            self.initial_data.get(CONF_KNX_TUNNEL_ENDPOINT_IA),
        )

    async def async_step_connection_type(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle connection type configuration."""
        if user_input is not None:
            if self._async_scan_gen:
                await self._async_scan_gen.aclose()  # stop the scan
                self._async_scan_gen = None
            if self._gatewayscanner:
                self._found_gateways = list(
                    self._gatewayscanner.found_gateways.values()
                )
            connection_type = user_input[CONF_KNX_CONNECTION_TYPE]
            if connection_type == CONF_KNX_ROUTING:
                return await self.async_step_routing()

            if connection_type == CONF_KNX_TUNNELING:
                self._found_tunnels = [
                    gateway
                    for gateway in self._found_gateways
                    if gateway.supports_tunnelling
                ]
                self._found_tunnels.sort(
                    key=lambda tunnel: tunnel.individual_address.raw
                    if tunnel.individual_address
                    else 0
                )
                return await self.async_step_tunnel()

            # Automatic connection type
            self.new_entry_data = KNXConfigEntryData(
                connection_type=CONF_KNX_AUTOMATIC,
                tunnel_endpoint_ia=None,
            )
            self.new_title = CONF_KNX_AUTOMATIC.capitalize()
            return self.finish_flow()

        supported_connection_types = {
            CONF_KNX_TUNNELING: CONF_KNX_TUNNELING.capitalize(),
            CONF_KNX_ROUTING: CONF_KNX_ROUTING.capitalize(),
        }

        if isinstance(self, OptionsFlow) and (knx_module := self.hass.data.get(DOMAIN)):
            xknx = knx_module.xknx
        else:
            xknx = XKNX()
        self._gatewayscanner = GatewayScanner(
            xknx, stop_on_found=0, timeout_in_seconds=2
        )
        # keep a reference to the generator to scan in background until user selects a connection type
        self._async_scan_gen = self._gatewayscanner.async_scan()
        try:
            await anext(self._async_scan_gen)
        except StopAsyncIteration:
            pass  # scan finished, no interfaces discovered
        else:
            # add automatic at first position only if a gateway responded
            supported_connection_types = {
                CONF_KNX_AUTOMATIC: CONF_KNX_AUTOMATIC.capitalize()
            } | supported_connection_types

        fields = {
            vol.Required(CONF_KNX_CONNECTION_TYPE): vol.In(supported_connection_types)
        }
        return self.async_show_form(
            step_id="connection_type", data_schema=vol.Schema(fields)
        )

    async def async_step_tunnel(self, user_input: dict | None = None) -> FlowResult:
        """Select a tunnel from a list.

        Will be skipped if the gateway scan was unsuccessful
        or if only one gateway was found.
        """
        if user_input is not None:
            if user_input[CONF_KNX_GATEWAY] == OPTION_MANUAL_TUNNEL:
                if self._found_tunnels:
                    self._selected_tunnel = self._found_tunnels[0]
                return await self.async_step_manual_tunnel()

            self._selected_tunnel = next(
                tunnel
                for tunnel in self._found_tunnels
                if user_input[CONF_KNX_GATEWAY] == str(tunnel)
            )
            connection_type = (
                CONF_KNX_TUNNELING_TCP_SECURE
                if self._selected_tunnel.tunnelling_requires_secure
                else CONF_KNX_TUNNELING_TCP
                if self._selected_tunnel.supports_tunnelling_tcp
                else CONF_KNX_TUNNELING
            )
            self.new_entry_data = KNXConfigEntryData(
                host=self._selected_tunnel.ip_addr,
                port=self._selected_tunnel.port,
                route_back=False,
                connection_type=connection_type,
                device_authentication=None,
                user_id=None,
                user_password=None,
                tunnel_endpoint_ia=None,
            )
            if connection_type == CONF_KNX_TUNNELING_TCP_SECURE:
                return self.async_show_menu(
                    step_id="secure_key_source",
                    menu_options=["secure_knxkeys", "secure_tunnel_manual"],
                )
            self.new_title = f"Tunneling @ {self._selected_tunnel}"
            return self.finish_flow()

        if not self._found_tunnels:
            return await self.async_step_manual_tunnel()

        errors: dict = {}
        tunnel_options = {
            str(tunnel): f"{tunnel}{' 🔐' if tunnel.tunnelling_requires_secure else ''}"
            for tunnel in self._found_tunnels
        }
        tunnel_options |= {OPTION_MANUAL_TUNNEL: OPTION_MANUAL_TUNNEL}
        fields = {vol.Required(CONF_KNX_GATEWAY): vol.In(tunnel_options)}

        return self.async_show_form(
            step_id="tunnel", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_manual_tunnel(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manually configure tunnel connection parameters. Fields default to preselected gateway if one was found."""
        errors: dict = {}

        if user_input is not None:
            try:
                _host = user_input[CONF_HOST]
                _host_ip = await xknx_validate_ip(_host)
                ip_v4_validator(_host_ip, multicast=False)
            except (vol.Invalid, XKNXException):
                errors[CONF_HOST] = "invalid_ip_address"

            _local_ip = None
            if _local := user_input.get(CONF_KNX_LOCAL_IP):
                try:
                    _local_ip = await xknx_validate_ip(_local)
                    ip_v4_validator(_local_ip, multicast=False)
                except (vol.Invalid, XKNXException):
                    errors[CONF_KNX_LOCAL_IP] = "invalid_ip_address"

            selected_tunnelling_type = user_input[CONF_KNX_TUNNELING_TYPE]
            if not errors:
                try:
                    self._selected_tunnel = await request_description(
                        gateway_ip=_host_ip,
                        gateway_port=user_input[CONF_PORT],
                        local_ip=_local_ip,
                        route_back=user_input[CONF_KNX_ROUTE_BACK],
                    )
                except CommunicationError:
                    errors["base"] = "cannot_connect"
                else:
                    if bool(self._selected_tunnel.tunnelling_requires_secure) is not (
                        selected_tunnelling_type == CONF_KNX_TUNNELING_TCP_SECURE
                    ):
                        errors[CONF_KNX_TUNNELING_TYPE] = "unsupported_tunnel_type"
                    elif (
                        selected_tunnelling_type == CONF_KNX_TUNNELING_TCP
                        and not self._selected_tunnel.supports_tunnelling_tcp
                    ):
                        errors[CONF_KNX_TUNNELING_TYPE] = "unsupported_tunnel_type"

            if not errors:
                self.new_entry_data = KNXConfigEntryData(
                    connection_type=selected_tunnelling_type,
                    host=_host,
                    port=user_input[CONF_PORT],
                    route_back=user_input[CONF_KNX_ROUTE_BACK],
                    local_ip=_local,
                    device_authentication=None,
                    user_id=None,
                    user_password=None,
                    tunnel_endpoint_ia=None,
                )

                if selected_tunnelling_type == CONF_KNX_TUNNELING_TCP_SECURE:
                    return self.async_show_menu(
                        step_id="secure_key_source",
                        menu_options=["secure_knxkeys", "secure_tunnel_manual"],
                    )
                self.new_title = (
                    "Tunneling "
                    f"{'UDP' if selected_tunnelling_type == CONF_KNX_TUNNELING else 'TCP'} "
                    f"@ {_host}"
                )
                return self.finish_flow()

        _reconfiguring_existing_tunnel = (
            self.initial_data.get(CONF_KNX_CONNECTION_TYPE)
            in CONF_KNX_TUNNELING_TYPE_LABELS
        )
        if (  # initial attempt on ConfigFlow or coming from automatic / routing
            (isinstance(self, ConfigFlow) or not _reconfiguring_existing_tunnel)
            and not user_input
            and self._selected_tunnel is not None
        ):  # default to first found tunnel
            ip_address = self._selected_tunnel.ip_addr
            port = self._selected_tunnel.port
            if self._selected_tunnel.tunnelling_requires_secure:
                default_type = CONF_KNX_TUNNELING_TCP_SECURE
            elif self._selected_tunnel.supports_tunnelling_tcp:
                default_type = CONF_KNX_TUNNELING_TCP
            else:
                default_type = CONF_KNX_TUNNELING
        else:  # OptionFlow, no tunnel discovered or user input
            ip_address = (
                user_input[CONF_HOST]
                if user_input
                else self.initial_data.get(CONF_HOST)
            )
            port = (
                user_input[CONF_PORT]
                if user_input
                else self.initial_data.get(CONF_PORT, DEFAULT_MCAST_PORT)
            )
            default_type = (
                user_input[CONF_KNX_TUNNELING_TYPE]
                if user_input
                else self.initial_data[CONF_KNX_CONNECTION_TYPE]
                if _reconfiguring_existing_tunnel
                else CONF_KNX_TUNNELING
            )
        _route_back: bool = self.initial_data.get(
            CONF_KNX_ROUTE_BACK, not bool(self._selected_tunnel)
        )

        fields = {
            vol.Required(CONF_KNX_TUNNELING_TYPE, default=default_type): vol.In(
                CONF_KNX_TUNNELING_TYPE_LABELS
            ),
            vol.Required(CONF_HOST, default=ip_address): _IP_SELECTOR,
            vol.Required(CONF_PORT, default=port): _PORT_SELECTOR,
            vol.Required(
                CONF_KNX_ROUTE_BACK, default=_route_back
            ): selector.BooleanSelector(),
        }
        if self.show_advanced_options:
            fields[vol.Optional(CONF_KNX_LOCAL_IP)] = _IP_SELECTOR

        if not self._found_tunnels and not errors.get("base"):
            errors["base"] = "no_tunnel_discovered"
        return self.async_show_form(
            step_id="manual_tunnel", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_secure_tunnel_manual(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure ip secure tunnelling manually."""
        errors: dict = {}

        if user_input is not None:
            self.new_entry_data |= KNXConfigEntryData(
                device_authentication=user_input[CONF_KNX_SECURE_DEVICE_AUTHENTICATION],
                user_id=user_input[CONF_KNX_SECURE_USER_ID],
                user_password=user_input[CONF_KNX_SECURE_USER_PASSWORD],
                tunnel_endpoint_ia=None,
            )
            self.new_title = f"Secure Tunneling @ {self.new_entry_data[CONF_HOST]}"
            return self.finish_flow()

        fields = {
            vol.Required(
                CONF_KNX_SECURE_USER_ID,
                default=self.initial_data.get(CONF_KNX_SECURE_USER_ID, 2),
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=127, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_KNX_SECURE_USER_PASSWORD,
                default=self.initial_data.get(CONF_KNX_SECURE_USER_PASSWORD),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
            ),
            vol.Required(
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
                default=self.initial_data.get(CONF_KNX_SECURE_DEVICE_AUTHENTICATION),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
            ),
        }

        return self.async_show_form(
            step_id="secure_tunnel_manual",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_secure_routing_manual(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure ip secure routing manually."""
        errors: dict = {}

        if user_input is not None:
            try:
                key_bytes = bytes.fromhex(user_input[CONF_KNX_ROUTING_BACKBONE_KEY])
                if len(key_bytes) != 16:
                    raise ValueError
            except ValueError:
                errors[CONF_KNX_ROUTING_BACKBONE_KEY] = "invalid_backbone_key"
            if not errors:
                self.new_entry_data |= KNXConfigEntryData(
                    backbone_key=user_input[CONF_KNX_ROUTING_BACKBONE_KEY],
                    sync_latency_tolerance=user_input[
                        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE
                    ],
                )
                self.new_title = f"Secure Routing as {self.new_entry_data[CONF_KNX_INDIVIDUAL_ADDRESS]}"
                return self.finish_flow()

        fields = {
            vol.Required(
                CONF_KNX_ROUTING_BACKBONE_KEY,
                default=self.initial_data.get(CONF_KNX_ROUTING_BACKBONE_KEY),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
            ),
            vol.Required(
                CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
                default=self.initial_data.get(CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE)
                or 1000,
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=400,
                        max=4000,
                        unit_of_measurement="ms",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Coerce(int),
            ),
        }

        return self.async_show_form(
            step_id="secure_routing_manual",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_secure_knxkeys(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage upload of new KNX Keyring file."""
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_KNX_KNXKEY_PASSWORD]
            try:
                self._keyring = await save_uploaded_knxkeys_file(
                    self.hass,
                    uploaded_file_id=user_input[CONF_KEYRING_FILE],
                    password=password,
                )
            except InvalidSecureConfiguration:
                errors[CONF_KNX_KNXKEY_PASSWORD] = "keyfile_invalid_signature"

            if not errors and self._keyring:
                self.new_entry_data |= KNXConfigEntryData(
                    knxkeys_filename=f"{DOMAIN}/{DEFAULT_KNX_KEYRING_FILENAME}",
                    knxkeys_password=password,
                    backbone_key=None,
                    sync_latency_tolerance=None,
                )
                # Routing
                if self.connection_type in (CONF_KNX_ROUTING, CONF_KNX_ROUTING_SECURE):
                    return self.finish_flow()

                # Tunneling / Automatic
                # skip selection step if we have a keyfile update that includes a configured tunnel
                if self.tunnel_endpoint_ia is not None and self.tunnel_endpoint_ia in [
                    str(_if.individual_address) for _if in self._keyring.interfaces
                ]:
                    return self.finish_flow()
                if not errors:
                    return await self.async_step_knxkeys_tunnel_select()

        fields = {
            vol.Required(CONF_KEYRING_FILE): selector.FileSelector(
                config=selector.FileSelectorConfig(accept=".knxkeys")
            ),
            vol.Required(
                CONF_KNX_KNXKEY_PASSWORD,
                default=self.initial_data.get(CONF_KNX_KNXKEY_PASSWORD),
            ): selector.TextSelector(),
        }
        return self.async_show_form(
            step_id="secure_knxkeys",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_knxkeys_tunnel_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select if a specific tunnel should be used from knxkeys file."""
        errors = {}
        description_placeholders = {}
        if user_input is not None:
            selected_tunnel_ia: str | None = None
            _if_user_id: int | None = None
            if user_input[CONF_KNX_TUNNEL_ENDPOINT_IA] == CONF_KNX_AUTOMATIC:
                self.new_entry_data |= KNXConfigEntryData(
                    tunnel_endpoint_ia=None,
                )
            else:
                selected_tunnel_ia = user_input[CONF_KNX_TUNNEL_ENDPOINT_IA]
                self.new_entry_data |= KNXConfigEntryData(
                    tunnel_endpoint_ia=selected_tunnel_ia,
                    user_id=None,
                    user_password=None,
                    device_authentication=None,
                )
                _if_user_id = next(
                    (
                        _if.user_id
                        for _if in self._tunnel_endpoints
                        if str(_if.individual_address) == selected_tunnel_ia
                    ),
                    None,
                )
            _tunnel_identifier = selected_tunnel_ia or self.new_entry_data.get(
                CONF_HOST
            )
            _tunnel_suffix = f" @ {_tunnel_identifier}" if _tunnel_identifier else ""
            self.new_title = (
                f"{'Secure ' if _if_user_id else ''}Tunneling{_tunnel_suffix}"
            )
            return self.finish_flow()

        # this step is only called from async_step_secure_knxkeys so self._keyring is always set
        assert self._keyring

        # Filter for selected tunnel
        if self._selected_tunnel is not None:
            if host_ia := self._selected_tunnel.individual_address:
                self._tunnel_endpoints = self._keyring.get_tunnel_interfaces_by_host(
                    host=host_ia
                )
            if not self._tunnel_endpoints:
                errors["base"] = "keyfile_no_tunnel_for_host"
                description_placeholders = {CONF_HOST: str(host_ia)}
        else:
            self._tunnel_endpoints = self._keyring.interfaces

        tunnel_endpoint_options = [
            selector.SelectOptionDict(
                value=CONF_KNX_AUTOMATIC, label=CONF_KNX_AUTOMATIC.capitalize()
            )
        ]
        for endpoint in self._tunnel_endpoints:
            tunnel_endpoint_options.append(
                selector.SelectOptionDict(
                    value=str(endpoint.individual_address),
                    label=(
                        f"{endpoint.individual_address} "
                        f"{'🔐 ' if endpoint.user_id else ''}"
                        f"(Data Secure GAs: {len(endpoint.group_addresses)})"
                    ),
                )
            )
        return self.async_show_form(
            step_id="knxkeys_tunnel_select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_KNX_TUNNEL_ENDPOINT_IA, default=CONF_KNX_AUTOMATIC
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=tunnel_endpoint_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_routing(self, user_input: dict | None = None) -> FlowResult:
        """Routing setup."""
        errors: dict = {}
        _individual_address = (
            user_input[CONF_KNX_INDIVIDUAL_ADDRESS]
            if user_input
            else self.initial_data[CONF_KNX_INDIVIDUAL_ADDRESS]
        )
        _multicast_group = (
            user_input[CONF_KNX_MCAST_GRP]
            if user_input
            else self.initial_data[CONF_KNX_MCAST_GRP]
        )
        _multicast_port = (
            user_input[CONF_KNX_MCAST_PORT]
            if user_input
            else self.initial_data[CONF_KNX_MCAST_PORT]
        )

        if user_input is not None:
            try:
                ia_validator(_individual_address)
            except vol.Invalid:
                errors[CONF_KNX_INDIVIDUAL_ADDRESS] = "invalid_individual_address"
            try:
                ip_v4_validator(_multicast_group, multicast=True)
            except vol.Invalid:
                errors[CONF_KNX_MCAST_GRP] = "invalid_ip_address"
            if _local := user_input.get(CONF_KNX_LOCAL_IP):
                try:
                    _local_ip = await xknx_validate_ip(_local)
                    ip_v4_validator(_local_ip, multicast=False)
                except (vol.Invalid, XKNXException):
                    errors[CONF_KNX_LOCAL_IP] = "invalid_ip_address"

            if not errors:
                connection_type = (
                    CONF_KNX_ROUTING_SECURE
                    if user_input[CONF_KNX_ROUTING_SECURE]
                    else CONF_KNX_ROUTING
                )
                self.new_entry_data = KNXConfigEntryData(
                    connection_type=connection_type,
                    individual_address=_individual_address,
                    multicast_group=_multicast_group,
                    multicast_port=_multicast_port,
                    local_ip=_local,
                    device_authentication=None,
                    user_id=None,
                    user_password=None,
                    tunnel_endpoint_ia=None,
                )
                if connection_type == CONF_KNX_ROUTING_SECURE:
                    self.new_title = f"Secure Routing as {_individual_address}"
                    return self.async_show_menu(
                        step_id="secure_key_source",
                        menu_options=["secure_knxkeys", "secure_routing_manual"],
                    )
                self.new_title = f"Routing as {_individual_address}"
                return self.finish_flow()

        routers = [router for router in self._found_gateways if router.supports_routing]
        if not routers:
            errors["base"] = "no_router_discovered"
        default_secure_routing_enable = any(
            router for router in routers if router.routing_requires_secure
        )

        fields = {
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS, default=_individual_address
            ): _IA_SELECTOR,
            vol.Required(
                CONF_KNX_ROUTING_SECURE, default=default_secure_routing_enable
            ): selector.BooleanSelector(),
            vol.Required(CONF_KNX_MCAST_GRP, default=_multicast_group): _IP_SELECTOR,
            vol.Required(CONF_KNX_MCAST_PORT, default=_multicast_port): _PORT_SELECTOR,
        }
        if self.show_advanced_options:
            # Optional with default doesn't work properly in flow UI
            fields[vol.Optional(CONF_KNX_LOCAL_IP)] = _IP_SELECTOR

        return self.async_show_form(
            step_id="routing", data_schema=vol.Schema(fields), errors=errors
        )


class KNXConfigFlow(KNXCommonFlow, ConfigFlow, domain=DOMAIN):
    """Handle a KNX config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize KNX options flow."""
        super().__init__(initial_data=DEFAULT_ENTRY_DATA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> KNXOptionsFlow:
        """Get the options flow for this handler."""
        return KNXOptionsFlow(config_entry)

    @callback
    def finish_flow(self) -> FlowResult:
        """Create the ConfigEntry."""
        title = self.new_title or f"KNX {self.new_entry_data[CONF_KNX_CONNECTION_TYPE]}"
        return self.async_create_entry(
            title=title,
            data=DEFAULT_ENTRY_DATA | self.new_entry_data,
        )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_connection_type()


class KNXOptionsFlow(KNXCommonFlow, OptionsFlow):
    """Handle KNX options."""

    general_settings: dict

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize KNX options flow."""
        self.config_entry = config_entry
        super().__init__(initial_data=config_entry.data)  # type: ignore[arg-type]

    @callback
    def finish_flow(self) -> FlowResult:
        """Update the ConfigEntry and finish the flow."""
        new_data = DEFAULT_ENTRY_DATA | self.initial_data | self.new_entry_data
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
            title=self.new_title or UNDEFINED,
        )
        return self.async_create_entry(title="", data={})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage KNX options."""
        return self.async_show_menu(
            step_id="options_init",
            menu_options=[
                "connection_type",
                "communication_settings",
                "secure_knxkeys",
            ],
        )

    async def async_step_communication_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage KNX communication settings."""
        if user_input is not None:
            self.new_entry_data = KNXConfigEntryData(
                state_updater=user_input[CONF_KNX_STATE_UPDATER],
                rate_limit=user_input[CONF_KNX_RATE_LIMIT],
                telegram_log_size=user_input[CONF_KNX_TELEGRAM_LOG_SIZE],
            )
            return self.finish_flow()

        data_schema = {
            vol.Required(
                CONF_KNX_STATE_UPDATER,
                default=self.initial_data.get(
                    CONF_KNX_STATE_UPDATER, CONF_KNX_DEFAULT_STATE_UPDATER
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_KNX_RATE_LIMIT,
                default=self.initial_data.get(
                    CONF_KNX_RATE_LIMIT, CONF_KNX_DEFAULT_RATE_LIMIT
                ),
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=CONF_MAX_RATE_LIMIT,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_KNX_TELEGRAM_LOG_SIZE,
                default=self.initial_data.get(
                    CONF_KNX_TELEGRAM_LOG_SIZE, TELEGRAM_LOG_DEFAULT
                ),
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=TELEGRAM_LOG_MAX,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Coerce(int),
            ),
        }
        return self.async_show_form(
            step_id="communication_settings",
            data_schema=vol.Schema(data_schema),
            last_step=True,
            description_placeholders={
                "telegram_log_size_max": f"{TELEGRAM_LOG_MAX}",
            },
        )
