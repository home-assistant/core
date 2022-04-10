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
    CONF_KNX_INITIAL_CONNECTION_TYPES,
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

CONF_KNX_GATEWAY: Final = "gateway"
CONF_MAX_RATE_LIMIT: Final = 60
CONF_DEFAULT_LOCAL_IP: Final = "0.0.0.0"

DEFAULT_ENTRY_DATA: KNXConfigEntryData = {
    CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,
    CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
    CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
}

CONF_KNX_TUNNELING_TYPE: Final = "tunneling_type"
CONF_KNX_LABEL_TUNNELING_TCP: Final = "TCP"
CONF_KNX_LABEL_TUNNELING_TCP_SECURE: Final = "TCP with IP Secure"
CONF_KNX_LABEL_TUNNELING_UDP: Final = "UDP"
CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK: Final = "UDP with route back / NAT mode"

_IA_SELECTOR = selector.selector({"text": {}})
_IP_SELECTOR = selector.selector({"text": {}})
_PORT_SELECTOR = vol.All(
    selector.selector({"number": {"min": 1, "max": 65535, "mode": "box"}}),
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
                entry_data: KNXConfigEntryData = {
                    **DEFAULT_ENTRY_DATA,  # type: ignore[misc]
                    CONF_KNX_CONNECTION_TYPE: user_input[CONF_KNX_CONNECTION_TYPE],
                }
                return self.async_create_entry(
                    title=CONF_KNX_AUTOMATIC.capitalize(),
                    data=entry_data,
                )

            if connection_type == CONF_KNX_ROUTING:
                return await self.async_step_routing()

            if connection_type == CONF_KNX_TUNNELING and self._found_tunnels:
                return await self.async_step_tunnel()

            return await self.async_step_manual_tunnel()

        errors: dict = {}
        supported_connection_types = CONF_KNX_INITIAL_CONNECTION_TYPES.copy()
        gateways = await scan_for_gateways()

        if gateways:
            # add automatic only if a gateway responded
            supported_connection_types.insert(0, CONF_KNX_AUTOMATIC)
            self._found_tunnels = [
                gateway for gateway in gateways if gateway.supports_tunnelling
            ]

        fields = {
            vol.Required(CONF_KNX_CONNECTION_TYPE): vol.In(supported_connection_types)
        }

        return self.async_show_form(
            step_id="type", data_schema=vol.Schema(fields), errors=errors
        )

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
        if user_input is not None:
            connection_type = user_input[CONF_KNX_TUNNELING_TYPE]

            entry_data: KNXConfigEntryData = {
                **DEFAULT_ENTRY_DATA,  # type: ignore[misc]
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_KNX_ROUTE_BACK: (
                    connection_type == CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK
                ),
                CONF_KNX_LOCAL_IP: user_input.get(CONF_KNX_LOCAL_IP),
                CONF_KNX_CONNECTION_TYPE: (
                    CONF_KNX_TUNNELING_TCP
                    if connection_type == CONF_KNX_LABEL_TUNNELING_TCP
                    else CONF_KNX_TUNNELING
                ),
            }

            if connection_type == CONF_KNX_LABEL_TUNNELING_TCP_SECURE:
                self._tunneling_config = entry_data
                return self.async_show_menu(
                    step_id="secure_tunneling",
                    menu_options=["secure_knxkeys", "secure_manual"],
                )

            return self.async_create_entry(
                title=f"{CONF_KNX_TUNNELING.capitalize()} @ {user_input[CONF_HOST]}",
                data=entry_data,
            )

        errors: dict = {}
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
            entry_data: KNXConfigEntryData = {
                **self._tunneling_config,  # type: ignore[misc]
                CONF_KNX_SECURE_USER_ID: user_input[CONF_KNX_SECURE_USER_ID],
                CONF_KNX_SECURE_USER_PASSWORD: user_input[
                    CONF_KNX_SECURE_USER_PASSWORD
                ],
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION: user_input[
                    CONF_KNX_SECURE_DEVICE_AUTHENTICATION
                ],
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
            }

            return self.async_create_entry(
                title=f"Secure {CONF_KNX_TUNNELING.capitalize()} @ {self._tunneling_config[CONF_HOST]}",
                data=entry_data,
            )

        fields = {
            vol.Required(CONF_KNX_SECURE_USER_ID, default=2): vol.All(
                selector.selector({"number": {"min": 1, "max": 127, "mode": "box"}}),
                vol.Coerce(int),
            ),
            vol.Required(CONF_KNX_SECURE_USER_PASSWORD): selector.selector(
                {"text": {"type": "password"}}
            ),
            vol.Required(CONF_KNX_SECURE_DEVICE_AUTHENTICATION): selector.selector(
                {"text": {"type": "password"}}
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
            try:
                assert self._tunneling_config
                storage_key: str = (
                    CONST_KNX_STORAGE_KEY + user_input[CONF_KNX_KNXKEY_FILENAME]
                )
                load_key_ring(
                    self.hass.config.path(
                        STORAGE_DIR,
                        storage_key,
                    ),
                    user_input[CONF_KNX_KNXKEY_PASSWORD],
                )
                entry_data: KNXConfigEntryData = {
                    **self._tunneling_config,  # type: ignore[misc]
                    CONF_KNX_KNXKEY_FILENAME: storage_key,
                    CONF_KNX_KNXKEY_PASSWORD: user_input[CONF_KNX_KNXKEY_PASSWORD],
                    CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
                }

                return self.async_create_entry(
                    title=f"Secure {CONF_KNX_TUNNELING.capitalize()} @ {self._tunneling_config[CONF_HOST]}",
                    data=entry_data,
                )
            except InvalidSignature:
                errors["base"] = "invalid_signature"
            except FileNotFoundError:
                errors["base"] = "file_not_found"

        fields = {
            vol.Required(CONF_KNX_KNXKEY_FILENAME): selector.selector({"text": {}}),
            vol.Required(CONF_KNX_KNXKEY_PASSWORD): selector.selector({"text": {}}),
        }

        return self.async_show_form(
            step_id="secure_knxkeys", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_routing(self, user_input: dict | None = None) -> FlowResult:
        """Routing setup."""
        if user_input is not None:
            return self.async_create_entry(
                title=CONF_KNX_ROUTING.capitalize(),
                data={
                    **DEFAULT_ENTRY_DATA,
                    CONF_KNX_MCAST_GRP: user_input[CONF_KNX_MCAST_GRP],
                    CONF_KNX_MCAST_PORT: user_input[CONF_KNX_MCAST_PORT],
                    CONF_KNX_INDIVIDUAL_ADDRESS: user_input[
                        CONF_KNX_INDIVIDUAL_ADDRESS
                    ],
                    CONF_KNX_LOCAL_IP: user_input.get(CONF_KNX_LOCAL_IP),
                    CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
                },
            )

        errors: dict = {}
        fields = {
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS, default=XKNX.DEFAULT_ADDRESS
            ): _IA_SELECTOR,
            vol.Required(CONF_KNX_MCAST_GRP, default=DEFAULT_MCAST_GRP): _IP_SELECTOR,
            vol.Required(
                CONF_KNX_MCAST_PORT, default=DEFAULT_MCAST_PORT
            ): _PORT_SELECTOR,
        }

        if self.show_advanced_options:
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
            ): selector.selector({"text": {}}),
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
            ] = selector.selector({"boolean": {}})
            data_schema[
                vol.Required(
                    CONF_KNX_RATE_LIMIT,
                    default=self.current_config.get(
                        CONF_KNX_RATE_LIMIT,
                        CONF_KNX_DEFAULT_RATE_LIMIT,
                    ),
                )
            ] = vol.All(
                selector.selector(
                    {
                        "number": {
                            "min": 1,
                            "max": CONF_MAX_RATE_LIMIT,
                            "mode": "box",
                        }
                    }
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

        entry_data = {
            **DEFAULT_ENTRY_DATA,
            **self.general_settings,
            CONF_KNX_LOCAL_IP: self.general_settings.get(CONF_KNX_LOCAL_IP)
            if self.general_settings.get(CONF_KNX_LOCAL_IP) != CONF_DEFAULT_LOCAL_IP
            else None,
            CONF_HOST: self.current_config.get(CONF_HOST, ""),
        }

        if user_input is not None:
            connection_type = user_input[CONF_KNX_TUNNELING_TYPE]
            entry_data = {
                **entry_data,
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_KNX_ROUTE_BACK: (
                    connection_type == CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK
                ),
                CONF_KNX_CONNECTION_TYPE: (
                    CONF_KNX_TUNNELING_TCP
                    if connection_type == CONF_KNX_LABEL_TUNNELING_TCP
                    else CONF_KNX_TUNNELING
                ),
            }

        entry_title = str(entry_data[CONF_KNX_CONNECTION_TYPE]).capitalize()
        if entry_data[CONF_KNX_CONNECTION_TYPE] == CONF_KNX_TUNNELING:
            entry_title = f"{CONF_KNX_TUNNELING.capitalize()} @ {entry_data[CONF_HOST]}"
        if entry_data[CONF_KNX_CONNECTION_TYPE] == CONF_KNX_TUNNELING_TCP:
            entry_title = (
                f"{CONF_KNX_TUNNELING.capitalize()} (TCP) @ {entry_data[CONF_HOST]}"
            )

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
