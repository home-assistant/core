"""Config flow for KNX."""
from __future__ import annotations

from typing import Any, Final

import voluptuous as vol
from xknx import XKNX
from xknx.exceptions.exception import InvalidSignature
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.io.gateway_scanner import GatewayDescriptor, GatewayScanner
from xknx.secure import load_key_ring

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_FILENAME,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_ID,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    CONST_KNX_STORAGE_KEY,
    DOMAIN,
    KNXConfigEntryData,
)
from .schema import ia_validator, ip_v4_validator

CONF_KNX_GATEWAY: Final = "gateway"
CONF_MAX_RATE_LIMIT: Final = 60
CONF_DEFAULT_LOCAL_IP: Final = "0.0.0.0"

DEFAULT_ENTRY_DATA = KNXConfigEntryData(
    individual_address=XKNX.DEFAULT_ADDRESS,
    multicast_group=DEFAULT_MCAST_GRP,
    multicast_port=DEFAULT_MCAST_PORT,
    state_updater=CONF_KNX_DEFAULT_STATE_UPDATER,
    rate_limit=CONF_KNX_DEFAULT_RATE_LIMIT,
)

CONF_KNX_TUNNELING_TYPE: Final = "tunneling_type"
CONF_KNX_LABEL_TUNNELING_TCP: Final = "TCP"
CONF_KNX_LABEL_TUNNELING_TCP_SECURE: Final = "TCP with IP Secure"
CONF_KNX_LABEL_TUNNELING_UDP: Final = "UDP"
CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK: Final = "UDP with route back / NAT mode"

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


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a KNX config flow."""

    VERSION = 1

    _found_tunnels: list[GatewayDescriptor]
    _selected_tunnel: GatewayDescriptor | None
    _tunneling_config: KNXConfigEntryData | None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> KNXOptionsFlowHandler:
        """Get the options flow for this handler."""
        return KNXOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._found_tunnels = []
        self._selected_tunnel = None
        self._tunneling_config = None
        return await self.async_step_type()

    async def async_step_type(self, user_input: dict | None = None) -> FlowResult:
        """Handle connection type configuration."""
        if user_input is not None:
            connection_type = user_input[CONF_KNX_CONNECTION_TYPE]
            if connection_type == CONF_KNX_AUTOMATIC:
                entry_data = DEFAULT_ENTRY_DATA | KNXConfigEntryData(
                    connection_type=CONF_KNX_AUTOMATIC
                )
                return self.async_create_entry(
                    title=CONF_KNX_AUTOMATIC.capitalize(),
                    data=entry_data,
                )

            if connection_type == CONF_KNX_ROUTING:
                return await self.async_step_routing()

            if connection_type == CONF_KNX_TUNNELING and self._found_tunnels:
                return await self.async_step_tunnel()

            return await self.async_step_manual_tunnel()

        supported_connection_types = {
            CONF_KNX_TUNNELING: CONF_KNX_TUNNELING.capitalize(),
            CONF_KNX_ROUTING: CONF_KNX_ROUTING.capitalize(),
        }
        if gateways := await scan_for_gateways():
            # add automatic at first position only if a gateway responded
            supported_connection_types = {
                CONF_KNX_AUTOMATIC: CONF_KNX_AUTOMATIC.capitalize()
            } | supported_connection_types
            self._found_tunnels = [
                gateway for gateway in gateways if gateway.supports_tunnelling
            ]

        fields = {
            vol.Required(CONF_KNX_CONNECTION_TYPE): vol.In(supported_connection_types)
        }
        return self.async_show_form(step_id="type", data_schema=vol.Schema(fields))

    async def async_step_tunnel(self, user_input: dict | None = None) -> FlowResult:
        """Select a tunnel from a list. Will be skipped if the gateway scan was unsuccessful or if only one gateway was found."""
        if user_input is not None:
            self._selected_tunnel = next(
                tunnel
                for tunnel in self._found_tunnels
                if user_input[CONF_KNX_GATEWAY] == str(tunnel)
            )
            return await self.async_step_manual_tunnel()

        #  skip this step if the user has only one unique gateway.
        if len(self._found_tunnels) == 1:
            self._selected_tunnel = self._found_tunnels[0]
            return await self.async_step_manual_tunnel()

        errors: dict = {}
        tunnels_repr = {str(tunnel) for tunnel in self._found_tunnels}
        fields = {vol.Required(CONF_KNX_GATEWAY): vol.In(tunnels_repr)}

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
                _host = ip_v4_validator(user_input[CONF_HOST], multicast=False)
            except vol.Invalid:
                errors[CONF_HOST] = "invalid_ip_address"

            if _local_ip := user_input.get(CONF_KNX_LOCAL_IP):
                try:
                    _local_ip = ip_v4_validator(_local_ip, multicast=False)
                except vol.Invalid:
                    errors[CONF_KNX_LOCAL_IP] = "invalid_ip_address"

            if not errors:
                connection_type = user_input[CONF_KNX_TUNNELING_TYPE]
                entry_data = DEFAULT_ENTRY_DATA | KNXConfigEntryData(
                    host=_host,
                    port=user_input[CONF_PORT],
                    route_back=(
                        connection_type == CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK
                    ),
                    local_ip=_local_ip,
                    connection_type=(
                        CONF_KNX_TUNNELING_TCP
                        if connection_type == CONF_KNX_LABEL_TUNNELING_TCP
                        else CONF_KNX_TUNNELING
                    ),
                )

                if connection_type == CONF_KNX_LABEL_TUNNELING_TCP_SECURE:
                    self._tunneling_config = entry_data
                    return self.async_show_menu(
                        step_id="secure_tunneling",
                        menu_options=["secure_knxkeys", "secure_manual"],
                    )

                return self.async_create_entry(
                    title=f"Tunneling @ {_host}",
                    data=entry_data,
                )

        connection_methods: list[str] = [
            CONF_KNX_LABEL_TUNNELING_TCP,
            CONF_KNX_LABEL_TUNNELING_UDP,
            CONF_KNX_LABEL_TUNNELING_TCP_SECURE,
            CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK,
        ]
        ip_address = ""
        port = DEFAULT_MCAST_PORT
        if self._selected_tunnel is not None:
            ip_address = self._selected_tunnel.ip_addr
            port = self._selected_tunnel.port
            if not self._selected_tunnel.supports_tunnelling_tcp:
                connection_methods.remove(CONF_KNX_LABEL_TUNNELING_TCP)
                connection_methods.remove(CONF_KNX_LABEL_TUNNELING_TCP_SECURE)

        fields = {
            vol.Required(CONF_KNX_TUNNELING_TYPE): vol.In(connection_methods),
            vol.Required(CONF_HOST, default=ip_address): _IP_SELECTOR,
            vol.Required(CONF_PORT, default=port): _PORT_SELECTOR,
        }

        if self.show_advanced_options:
            fields[vol.Optional(CONF_KNX_LOCAL_IP)] = _IP_SELECTOR

        return self.async_show_form(
            step_id="manual_tunnel", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_secure_manual(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure ip secure manually."""
        errors: dict = {}

        if user_input is not None:
            assert self._tunneling_config
            entry_data = self._tunneling_config | KNXConfigEntryData(
                connection_type=CONF_KNX_TUNNELING_TCP_SECURE,
                device_authentication=user_input[CONF_KNX_SECURE_DEVICE_AUTHENTICATION],
                user_id=user_input[CONF_KNX_SECURE_USER_ID],
                user_password=user_input[CONF_KNX_SECURE_USER_PASSWORD],
            )

            return self.async_create_entry(
                title=f"Secure Tunneling @ {self._tunneling_config[CONF_HOST]}",
                data=entry_data,
            )

        fields = {
            vol.Required(CONF_KNX_SECURE_USER_ID, default=2): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=127, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                vol.Coerce(int),
            ),
            vol.Required(CONF_KNX_SECURE_USER_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
            ),
            vol.Required(CONF_KNX_SECURE_DEVICE_AUTHENTICATION): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
            ),
        }

        return self.async_show_form(
            step_id="secure_manual", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_secure_knxkeys(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure secure knxkeys used to authenticate."""
        errors = {}

        if user_input is not None:
            assert self._tunneling_config
            storage_key = CONST_KNX_STORAGE_KEY + user_input[CONF_KNX_KNXKEY_FILENAME]
            try:
                load_key_ring(
                    path=self.hass.config.path(STORAGE_DIR, storage_key),
                    password=user_input[CONF_KNX_KNXKEY_PASSWORD],
                )
            except FileNotFoundError:
                errors[CONF_KNX_KNXKEY_FILENAME] = "file_not_found"
            except InvalidSignature:
                errors[CONF_KNX_KNXKEY_PASSWORD] = "invalid_signature"

            if not errors:
                entry_data = self._tunneling_config | KNXConfigEntryData(
                    connection_type=CONF_KNX_TUNNELING_TCP_SECURE,
                    knxkeys_filename=storage_key,
                    knxkeys_password=user_input[CONF_KNX_KNXKEY_PASSWORD],
                )

                return self.async_create_entry(
                    title=f"Secure Tunneling @ {self._tunneling_config[CONF_HOST]}",
                    data=entry_data,
                )

        fields = {
            vol.Required(CONF_KNX_KNXKEY_FILENAME): selector.TextSelector(),
            vol.Required(CONF_KNX_KNXKEY_PASSWORD): selector.TextSelector(),
        }

        return self.async_show_form(
            step_id="secure_knxkeys", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_routing(self, user_input: dict | None = None) -> FlowResult:
        """Routing setup."""
        errors: dict = {}
        _individual_address = (
            user_input[CONF_KNX_INDIVIDUAL_ADDRESS]
            if user_input
            else XKNX.DEFAULT_ADDRESS
        )
        _multicast_group = (
            user_input[CONF_KNX_MCAST_GRP] if user_input else DEFAULT_MCAST_GRP
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
            if _local_ip := user_input.get(CONF_KNX_LOCAL_IP):
                try:
                    ip_v4_validator(_local_ip, multicast=False)
                except vol.Invalid:
                    errors[CONF_KNX_LOCAL_IP] = "invalid_ip_address"

            if not errors:
                entry_data = DEFAULT_ENTRY_DATA | KNXConfigEntryData(
                    connection_type=CONF_KNX_ROUTING,
                    individual_address=_individual_address,
                    multicast_group=_multicast_group,
                    multicast_port=user_input[CONF_KNX_MCAST_PORT],
                    local_ip=_local_ip,
                )
                return self.async_create_entry(
                    title=CONF_KNX_ROUTING.capitalize(), data=entry_data
                )

        fields = {
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS, default=_individual_address
            ): _IA_SELECTOR,
            vol.Required(CONF_KNX_MCAST_GRP, default=_multicast_group): _IP_SELECTOR,
            vol.Required(
                CONF_KNX_MCAST_PORT, default=DEFAULT_MCAST_PORT
            ): _PORT_SELECTOR,
        }

        if self.show_advanced_options:
            # Optional with default doesn't work properly in flow UI
            fields[vol.Optional(CONF_KNX_LOCAL_IP)] = _IP_SELECTOR

        return self.async_show_form(
            step_id="routing", data_schema=vol.Schema(fields), errors=errors
        )


class KNXOptionsFlowHandler(OptionsFlow):
    """Handle KNX options."""

    general_settings: dict
    current_config: dict

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize KNX options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage KNX options."""
        if user_input is not None:
            self.general_settings = user_input
            return await self.async_step_tunnel()

        supported_connection_types = [
            CONF_KNX_AUTOMATIC,
            CONF_KNX_TUNNELING,
            CONF_KNX_ROUTING,
        ]
        self.current_config = self.config_entry.data  # type: ignore[assignment]

        data_schema = {
            vol.Required(
                CONF_KNX_CONNECTION_TYPE,
                default=(
                    CONF_KNX_TUNNELING
                    if self.current_config.get(CONF_KNX_CONNECTION_TYPE)
                    == CONF_KNX_TUNNELING_TCP
                    else self.current_config.get(CONF_KNX_CONNECTION_TYPE)
                ),
            ): vol.In(supported_connection_types),
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS,
                default=self.current_config[CONF_KNX_INDIVIDUAL_ADDRESS],
            ): selector.TextSelector(),
            vol.Required(
                CONF_KNX_MCAST_GRP,
                default=self.current_config.get(CONF_KNX_MCAST_GRP, DEFAULT_MCAST_GRP),
            ): _IP_SELECTOR,
            vol.Required(
                CONF_KNX_MCAST_PORT,
                default=self.current_config.get(
                    CONF_KNX_MCAST_PORT, DEFAULT_MCAST_PORT
                ),
            ): _PORT_SELECTOR,
        }

        if self.show_advanced_options:
            local_ip = (
                self.current_config.get(CONF_KNX_LOCAL_IP)
                if self.current_config.get(CONF_KNX_LOCAL_IP) is not None
                else CONF_DEFAULT_LOCAL_IP
            )
            data_schema[
                vol.Required(
                    CONF_KNX_LOCAL_IP,
                    default=local_ip,
                )
            ] = _IP_SELECTOR
            data_schema[
                vol.Required(
                    CONF_KNX_STATE_UPDATER,
                    default=self.current_config.get(
                        CONF_KNX_STATE_UPDATER,
                        CONF_KNX_DEFAULT_STATE_UPDATER,
                    ),
                )
            ] = selector.BooleanSelector()
            data_schema[
                vol.Required(
                    CONF_KNX_RATE_LIMIT,
                    default=self.current_config.get(
                        CONF_KNX_RATE_LIMIT,
                        CONF_KNX_DEFAULT_RATE_LIMIT,
                    ),
                )
            ] = vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=CONF_MAX_RATE_LIMIT,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Coerce(int),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            last_step=self.current_config.get(CONF_KNX_CONNECTION_TYPE)
            != CONF_KNX_TUNNELING,
        )

    async def async_step_tunnel(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage KNX tunneling options."""
        if (
            self.general_settings.get(CONF_KNX_CONNECTION_TYPE) == CONF_KNX_TUNNELING
            and user_input is None
        ):
            connection_methods: list[str] = [
                CONF_KNX_LABEL_TUNNELING_TCP,
                CONF_KNX_LABEL_TUNNELING_UDP,
                CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK,
            ]
            return self.async_show_form(
                step_id="tunnel",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_KNX_TUNNELING_TYPE,
                            default=get_knx_tunneling_type(self.current_config),
                        ): vol.In(connection_methods),
                        vol.Required(
                            CONF_HOST, default=self.current_config.get(CONF_HOST)
                        ): _IP_SELECTOR,
                        vol.Required(
                            CONF_PORT, default=self.current_config.get(CONF_PORT, 3671)
                        ): _PORT_SELECTOR,
                    }
                ),
                last_step=True,
            )

        _local_ip = self.general_settings.get(CONF_KNX_LOCAL_IP)
        entry_data = (
            DEFAULT_ENTRY_DATA
            | self.general_settings
            | KNXConfigEntryData(
                host=self.current_config.get(CONF_HOST, ""),
                local_ip=_local_ip if _local_ip != CONF_DEFAULT_LOCAL_IP else None,
            )
        )

        if user_input is not None:
            connection_type = user_input[CONF_KNX_TUNNELING_TYPE]
            entry_data = entry_data | KNXConfigEntryData(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                route_back=(connection_type == CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK),
                connection_type=(
                    CONF_KNX_TUNNELING_TCP
                    if connection_type == CONF_KNX_LABEL_TUNNELING_TCP
                    else CONF_KNX_TUNNELING
                ),
            )

        entry_title = str(entry_data[CONF_KNX_CONNECTION_TYPE]).capitalize()
        if entry_data[CONF_KNX_CONNECTION_TYPE] == CONF_KNX_TUNNELING:
            entry_title = f"Tunneling @ {entry_data[CONF_HOST]}"
        if entry_data[CONF_KNX_CONNECTION_TYPE] == CONF_KNX_TUNNELING_TCP:
            entry_title = f"Tunneling @ {entry_data[CONF_HOST]} (TCP)"

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=entry_data,
            title=entry_title,
        )

        return self.async_create_entry(title="", data={})


def get_knx_tunneling_type(config_entry_data: dict) -> str:
    """Obtain the knx tunneling type based on the data in the config entry data."""
    connection_type = config_entry_data[CONF_KNX_CONNECTION_TYPE]
    route_back = config_entry_data.get(CONF_KNX_ROUTE_BACK, False)
    if route_back and connection_type == CONF_KNX_TUNNELING:
        return CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK
    if connection_type == CONF_KNX_TUNNELING_TCP:
        return CONF_KNX_LABEL_TUNNELING_TCP

    return CONF_KNX_LABEL_TUNNELING_UDP


async def scan_for_gateways(stop_on_found: int = 0) -> list[GatewayDescriptor]:
    """Scan for gateways within the network."""
    xknx = XKNX()
    gatewayscanner = GatewayScanner(
        xknx, stop_on_found=stop_on_found, timeout_in_seconds=2
    )
    return await gatewayscanner.scan()
