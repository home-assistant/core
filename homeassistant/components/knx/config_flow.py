"""Config flow for KNX."""
from __future__ import annotations

from typing import Any, Final

import voluptuous as vol
from xknx import XKNX
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.io.gateway_scanner import GatewayDescriptor, GatewayScanner

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_INITIAL_CONNECTION_TYPES,
    CONF_KNX_ROUTING,
    CONF_KNX_TUNNELING,
    DOMAIN,
)
from .schema import ConnectionSchema

CONF_KNX_GATEWAY: Final = "gateway"
CONF_MAX_RATE_LIMIT: Final = 60

DEFAULT_ENTRY_DATA: Final = {
    ConnectionSchema.CONF_KNX_STATE_UPDATER: ConnectionSchema.CONF_KNX_DEFAULT_STATE_UPDATER,
    ConnectionSchema.CONF_KNX_RATE_LIMIT: ConnectionSchema.CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,
    ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
    ConnectionSchema.CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
}


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a KNX config flow."""

    VERSION = 1

    _tunnels: list
    _gateway_ip: str = ""
    _gateway_port: int = DEFAULT_MCAST_PORT

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> KNXOptionsFlowHandler:
        """Get the options flow for this handler."""
        return KNXOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._tunnels = []
        return await self.async_step_type()

    async def async_step_type(self, user_input: dict | None = None) -> FlowResult:
        """Handle connection type configuration."""
        errors: dict = {}
        supported_connection_types = CONF_KNX_INITIAL_CONNECTION_TYPES.copy()
        fields = {}

        if user_input is None:
            gateways = await scan_for_gateways()

            if gateways:
                supported_connection_types.insert(0, CONF_KNX_AUTOMATIC)
                self._tunnels = [
                    gateway for gateway in gateways if gateway.supports_tunnelling
                ]

            fields = {
                vol.Required(CONF_KNX_CONNECTION_TYPE): vol.In(
                    supported_connection_types
                )
            }

        if user_input is not None:
            connection_type = user_input[CONF_KNX_CONNECTION_TYPE]
            if connection_type == CONF_KNX_AUTOMATIC:
                return self.async_create_entry(
                    title=CONF_KNX_AUTOMATIC.capitalize(),
                    data={**DEFAULT_ENTRY_DATA, **user_input},
                )

            if connection_type == CONF_KNX_ROUTING:
                return await self.async_step_routing()

            if connection_type == CONF_KNX_TUNNELING and self._tunnels:
                return await self.async_step_tunnel()

            return await self.async_step_manual_tunnel()

        return self.async_show_form(
            step_id="type", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_manual_tunnel(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """General setup."""
        errors: dict = {}

        if user_input is not None:
            return self.async_create_entry(
                title=f"{CONF_KNX_TUNNELING.capitalize()} @ {user_input[CONF_HOST]}",
                data={
                    **DEFAULT_ENTRY_DATA,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_KNX_INDIVIDUAL_ADDRESS: user_input[
                        CONF_KNX_INDIVIDUAL_ADDRESS
                    ],
                    ConnectionSchema.CONF_KNX_ROUTE_BACK: user_input[
                        ConnectionSchema.CONF_KNX_ROUTE_BACK
                    ],
                    CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                },
            )

        fields = {
            vol.Required(CONF_HOST, default=self._gateway_ip): str,
            vol.Required(CONF_PORT, default=self._gateway_port): vol.Coerce(int),
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS, default=XKNX.DEFAULT_ADDRESS
            ): str,
            vol.Required(
                ConnectionSchema.CONF_KNX_ROUTE_BACK, default=False
            ): vol.Coerce(bool),
        }

        return self.async_show_form(
            step_id="manual_tunnel", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_tunnel(self, user_input: dict | None = None) -> FlowResult:
        """Select a tunnel from a list. Will be skipped if the gateway scan was unsuccessful or if only one gateway was found."""
        errors: dict = {}

        if user_input is not None:
            gateway: GatewayDescriptor = next(
                gateway
                for gateway in self._tunnels
                if user_input[CONF_KNX_GATEWAY] == str(gateway)
            )

            self._gateway_ip = gateway.ip_addr
            self._gateway_port = gateway.port

            return await self.async_step_manual_tunnel()

        tunnel_repr = {
            str(tunnel) for tunnel in self._tunnels if tunnel.supports_tunnelling
        }

        #  skip this step if the user has only one unique gateway.
        if len(tunnel_repr) == 1:
            _gateway: GatewayDescriptor = self._tunnels[0]
            self._gateway_ip = _gateway.ip_addr
            self._gateway_port = _gateway.port
            return await self.async_step_manual_tunnel()

        fields = {vol.Required(CONF_KNX_GATEWAY): vol.In(tunnel_repr)}

        return self.async_show_form(
            step_id="tunnel", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_routing(self, user_input: dict | None = None) -> FlowResult:
        """Routing setup."""
        errors: dict = {}

        if user_input is not None:
            return self.async_create_entry(
                title=CONF_KNX_ROUTING.capitalize(),
                data={
                    **DEFAULT_ENTRY_DATA,
                    ConnectionSchema.CONF_KNX_MCAST_GRP: user_input[
                        ConnectionSchema.CONF_KNX_MCAST_GRP
                    ],
                    ConnectionSchema.CONF_KNX_MCAST_PORT: user_input[
                        ConnectionSchema.CONF_KNX_MCAST_PORT
                    ],
                    CONF_KNX_INDIVIDUAL_ADDRESS: user_input[
                        CONF_KNX_INDIVIDUAL_ADDRESS
                    ],
                    CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
                },
            )

        fields = {
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS, default=XKNX.DEFAULT_ADDRESS
            ): str,
            vol.Required(
                ConnectionSchema.CONF_KNX_MCAST_GRP, default=DEFAULT_MCAST_GRP
            ): str,
            vol.Required(
                ConnectionSchema.CONF_KNX_MCAST_PORT, default=DEFAULT_MCAST_PORT
            ): cv.port,
        }

        return self.async_show_form(
            step_id="routing", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_import(self, config: dict | None = None) -> FlowResult:
        """Import a config entry.

        Performs a one time import of the YAML configuration and creates a config entry based on it
        if not already done before.
        """
        if self._async_current_entries() or not config:
            return self.async_abort(reason="single_instance_allowed")

        data = {
            ConnectionSchema.CONF_KNX_RATE_LIMIT: min(
                config[ConnectionSchema.CONF_KNX_RATE_LIMIT], CONF_MAX_RATE_LIMIT
            ),
            ConnectionSchema.CONF_KNX_STATE_UPDATER: config[
                ConnectionSchema.CONF_KNX_STATE_UPDATER
            ],
            ConnectionSchema.CONF_KNX_MCAST_GRP: config[
                ConnectionSchema.CONF_KNX_MCAST_GRP
            ],
            ConnectionSchema.CONF_KNX_MCAST_PORT: config[
                ConnectionSchema.CONF_KNX_MCAST_PORT
            ],
            CONF_KNX_INDIVIDUAL_ADDRESS: config[CONF_KNX_INDIVIDUAL_ADDRESS],
        }

        if CONF_KNX_TUNNELING in config:
            return self.async_create_entry(
                title=f"{CONF_KNX_TUNNELING.capitalize()} @ {config[CONF_KNX_TUNNELING][CONF_HOST]}",
                data={
                    **DEFAULT_ENTRY_DATA,
                    CONF_HOST: config[CONF_KNX_TUNNELING][CONF_HOST],
                    CONF_PORT: config[CONF_KNX_TUNNELING][CONF_PORT],
                    ConnectionSchema.CONF_KNX_ROUTE_BACK: config[CONF_KNX_TUNNELING][
                        ConnectionSchema.CONF_KNX_ROUTE_BACK
                    ],
                    CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                    **data,
                },
            )

        if CONF_KNX_ROUTING in config:
            return self.async_create_entry(
                title=CONF_KNX_ROUTING.capitalize(),
                data={
                    **DEFAULT_ENTRY_DATA,
                    CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
                    **data,
                },
            )

        return self.async_create_entry(
            title=CONF_KNX_AUTOMATIC.capitalize(),
            data={
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                **data,
            },
        )


class KNXOptionsFlowHandler(OptionsFlow):
    """Handle KNX options."""

    general_settings: dict
    current_config: dict

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize KNX options flow."""
        self.config_entry = config_entry

    async def async_step_tunnel(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage KNX tunneling options."""
        if (
            self.general_settings.get(CONF_KNX_CONNECTION_TYPE) == CONF_KNX_TUNNELING
            and user_input is None
        ):
            return self.async_show_form(
                step_id="tunnel",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_HOST, default=self.current_config.get(CONF_HOST)
                        ): str,
                        vol.Required(
                            CONF_PORT, default=self.current_config.get(CONF_PORT, 3671)
                        ): cv.port,
                        vol.Required(
                            ConnectionSchema.CONF_KNX_ROUTE_BACK,
                            default=self.current_config.get(
                                ConnectionSchema.CONF_KNX_ROUTE_BACK, False
                            ),
                        ): vol.Coerce(bool),
                    }
                ),
                last_step=True,
            )

        entry_data = {
            **DEFAULT_ENTRY_DATA,
            **self.general_settings,
            CONF_HOST: self.current_config.get(CONF_HOST, ""),
        }

        if user_input is not None:
            entry_data = {
                **entry_data,
                **user_input,
            }

        entry_title = entry_data[CONF_KNX_CONNECTION_TYPE].capitalize()
        if entry_data[CONF_KNX_CONNECTION_TYPE] == CONF_KNX_TUNNELING:
            entry_title = f"{CONF_KNX_TUNNELING.capitalize()} @ {entry_data[CONF_HOST]}"

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=entry_data,
            title=entry_title,
        )

        return self.async_create_entry(title="", data={})

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
        self.current_config = self.config_entry.data  # type: ignore

        data_schema = {
            vol.Required(
                CONF_KNX_CONNECTION_TYPE,
                default=self.current_config.get(CONF_KNX_CONNECTION_TYPE),
            ): vol.In(supported_connection_types),
            vol.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS,
                default=self.current_config[CONF_KNX_INDIVIDUAL_ADDRESS],
            ): str,
            vol.Required(
                ConnectionSchema.CONF_KNX_MCAST_GRP,
                default=self.current_config.get(
                    ConnectionSchema.CONF_KNX_MCAST_GRP, DEFAULT_MCAST_GRP
                ),
            ): str,
            vol.Required(
                ConnectionSchema.CONF_KNX_MCAST_PORT,
                default=self.current_config.get(
                    ConnectionSchema.CONF_KNX_MCAST_PORT, DEFAULT_MCAST_PORT
                ),
            ): cv.port,
        }

        if self.show_advanced_options:
            data_schema[
                vol.Required(
                    ConnectionSchema.CONF_KNX_STATE_UPDATER,
                    default=self.current_config.get(
                        ConnectionSchema.CONF_KNX_STATE_UPDATER,
                        ConnectionSchema.CONF_KNX_DEFAULT_STATE_UPDATER,
                    ),
                )
            ] = bool
            data_schema[
                vol.Required(
                    ConnectionSchema.CONF_KNX_RATE_LIMIT,
                    default=self.current_config.get(
                        ConnectionSchema.CONF_KNX_RATE_LIMIT,
                        ConnectionSchema.CONF_KNX_DEFAULT_RATE_LIMIT,
                    ),
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=CONF_MAX_RATE_LIMIT))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            last_step=self.current_config.get(CONF_KNX_CONNECTION_TYPE)
            != CONF_KNX_TUNNELING,
        )


async def scan_for_gateways(stop_on_found: int = 0) -> list:
    """Scan for gateways within the network."""
    xknx = XKNX()
    gatewayscanner = GatewayScanner(
        xknx, stop_on_found=stop_on_found, timeout_in_seconds=2
    )
    return await gatewayscanner.scan()
