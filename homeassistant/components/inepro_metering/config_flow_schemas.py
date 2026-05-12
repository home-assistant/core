"""Schema builders for the Inepro Metering config flow."""

from typing import Any

from inepro_metering.routes import describe_route
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .bluetooth import DiscoveredGrowBluetoothMeter
from .config_flow_shared import (
    CONF_ACTION,
    CONF_DISCOVERED_BLUETOOTH_METER,
    CONF_DISCOVERED_METERS,
    CONF_SELECTED_METER,
    CONF_SELECTED_ROUTE,
    bluetooth_meter_key,
    discovered_meter_key,
    meter_slave_id_field,
    user_value,
)
from .const import (
    CONF_BAUDRATE,
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_BYTESIZE,
    CONF_DEVICE_KIND,
    CONF_DISCOVERED_GATEWAY,
    CONF_FAMILY,
    CONF_GATEWAY_DISCOVERY_TARGET,
    CONF_GATEWAY_SETUP_METHOD,
    CONF_PARITY,
    CONF_ROUTE_PURPOSE,
    CONF_SERIAL_PORT,
    CONF_SETUP_METHOD,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEFAULT_BAUDRATE,
    DEFAULT_BLE_PROXY_HOST,
    DEFAULT_BLE_PROXY_PORT,
    DEFAULT_BLUETOOTH_SCAN_INTERVAL,
    DEFAULT_BLUETOOTH_TIMEOUT,
    DEFAULT_BYTESIZE,
    DEFAULT_GATEWAY_SCAN_SLAVE_ID_END,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_SLAVE_ID_END,
    DEFAULT_STOPBITS,
    DEFAULT_TIMEOUT,
    DEVICE_KIND_GATEWAY,
    DEVICE_KIND_LABELS,
    DEVICE_KIND_METER,
    FAMILY_LABELS,
    GATEWAY_SETUP_METHOD_MANUAL_IP,
    GATEWAY_SETUP_METHOD_SCAN_NETWORK,
    ROUTE_PURPOSE_ACTIVE,
    ROUTE_PURPOSE_ONBOARDING,
    SETUP_METHOD_MANUAL,
    SETUP_METHOD_SCAN_BLUETOOTH,
    SETUP_METHOD_SCAN_SERIAL,
    SETUP_METHOD_SCAN_TCP_GATEWAY,
    TRANSPORT_LABELS,
    MeterFamily,
    TransportType,
)
from .discovery import (
    CONF_SLAVE_ID_END,
    CONF_SLAVE_ID_START,
    DiscoveredGrowMeter,
    DiscoveredTcpGateway,
)
from .entry_data import (
    ConfiguredMeter,
    ConfiguredRoute,
    build_route_key,
    get_bus_route_for_meter,
)
from .models import MeterProfile


def build_device_kind_schema() -> vol.Schema:
    """Build the initial selection form for what to add."""
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_KIND,
                default=DEVICE_KIND_METER,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": device_kind,
                            "label": DEVICE_KIND_LABELS[device_kind],
                        }
                        for device_kind in (DEVICE_KIND_METER, DEVICE_KIND_GATEWAY)
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        },
        extra=vol.ALLOW_EXTRA,
    )


def build_family_schema(
    supported_families: list[MeterFamily],
    default_family: MeterFamily,
) -> vol.Schema:
    """Build the meter family selection form."""
    return vol.Schema(
        {
            vol.Required(CONF_FAMILY, default=default_family.value): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": family_option.value,
                            "label": FAMILY_LABELS[family_option],
                        }
                        for family_option in supported_families
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def build_setup_method_schema() -> vol.Schema:
    """Build the setup method selection form for supported meters."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SETUP_METHOD,
                default=SETUP_METHOD_MANUAL,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": SETUP_METHOD_MANUAL,
                            "label": "Configure one meter manually",
                        },
                        {
                            "value": SETUP_METHOD_SCAN_SERIAL,
                            "label": "Scan a serial Modbus bus for meters",
                        },
                        {
                            "value": SETUP_METHOD_SCAN_TCP_GATEWAY,
                            "label": "Scan a Modbus TCP gateway for meters",
                        },
                        {
                            "value": SETUP_METHOD_SCAN_BLUETOOTH,
                            "label": "Add paired Bluetooth GROW meter",
                        },
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def build_gateway_setup_method_schema() -> vol.Schema:
    """Build the setup method selection form for TCP gateways."""
    return vol.Schema(
        {
            vol.Required(
                CONF_GATEWAY_SETUP_METHOD,
                default=GATEWAY_SETUP_METHOD_SCAN_NETWORK,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": GATEWAY_SETUP_METHOD_SCAN_NETWORK,
                            "label": "Search for inepro gateways (recommended)",
                        },
                        {
                            "value": GATEWAY_SETUP_METHOD_MANUAL_IP,
                            "label": "Enter gateway IP address manually",
                        },
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def build_gateway_discover_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Build the gateway discovery form with an optional explicit scan target."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_GATEWAY_DISCOVERY_TARGET,
                default=user_value(user_input, CONF_GATEWAY_DISCOVERY_TARGET, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        }
    )


def build_model_schema(
    profiles: dict[str, MeterProfile],
    default_variant: str,
) -> vol.Schema:
    """Build the meter model selection form for one family."""
    return vol.Schema(
        {
            vol.Optional(CONF_NAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_VARIANT, default=default_variant): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": variant,
                            "label": profile.title,
                        }
                        for variant, profile in profiles.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=DEFAULT_SCAN_INTERVAL,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


UNSELECTED_TRANSPORT = "__select_transport__"


def default_timeout_for_transport(transport: TransportType) -> int:
    """Return the default timeout for a transport form."""
    if transport in {TransportType.BLUETOOTH, TransportType.BLUETOOTH_PROXY}:
        return DEFAULT_BLUETOOTH_TIMEOUT
    return DEFAULT_TIMEOUT


def minimum_timeout_for_transport(transport: TransportType) -> int:
    """Return the minimum timeout selector value for a transport form."""
    if transport in {TransportType.BLUETOOTH, TransportType.BLUETOOTH_PROXY}:
        return DEFAULT_BLUETOOTH_TIMEOUT
    return 1


def build_transport_schema(
    supported_transports: tuple[TransportType, ...],
    *,
    selected_transport: str | None = None,
) -> vol.Schema:
    """Build the transport selection form for the chosen model."""
    default_value = (
        selected_transport
        if selected_transport in {transport.value for transport in supported_transports}
        else UNSELECTED_TRANSPORT
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_TRANSPORT,
                default=default_value,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": UNSELECTED_TRANSPORT,
                            "label": "Choose connection type",
                        },
                        *[
                            {
                                "value": transport.value,
                                "label": TRANSPORT_LABELS[transport],
                            }
                            for transport in supported_transports
                        ],
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def build_connection_schema(
    transport: TransportType,
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the connection form schema for the selected transport."""
    if transport is TransportType.SERIAL:
        return vol.Schema(
            {
                vol.Required(
                    CONF_SERIAL_PORT,
                    default=user_value(user_input, CONF_SERIAL_PORT, "COM1"),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_BAUDRATE,
                    default=user_value(user_input, CONF_BAUDRATE, DEFAULT_BAUDRATE),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=300,
                        max=115200,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_BYTESIZE,
                    default=user_value(user_input, CONF_BYTESIZE, DEFAULT_BYTESIZE),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=7,
                        max=8,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_PARITY,
                    default=user_value(user_input, CONF_PARITY, DEFAULT_PARITY),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "N", "label": "None"},
                            {"value": "E", "label": "Even"},
                            {"value": "O", "label": "Odd"},
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_STOPBITS,
                    default=user_value(user_input, CONF_STOPBITS, DEFAULT_STOPBITS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=2,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_TIMEOUT,
                    default=user_value(
                        user_input,
                        CONF_TIMEOUT,
                        DEFAULT_TIMEOUT,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=30,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    if transport is TransportType.BLUETOOTH:
        return vol.Schema(
            {
                vol.Required(
                    CONF_BLUETOOTH_ADDRESS,
                    default=user_value(user_input, CONF_BLUETOOTH_ADDRESS, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_BLUETOOTH_NAME,
                    default=user_value(user_input, CONF_BLUETOOTH_NAME, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_TIMEOUT,
                    default=user_value(
                        user_input,
                        CONF_TIMEOUT,
                        DEFAULT_BLUETOOTH_TIMEOUT,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10,
                        max=30,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    if transport is TransportType.BLUETOOTH_PROXY:
        return vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=user_value(user_input, CONF_HOST, DEFAULT_BLE_PROXY_HOST),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_PORT,
                    default=user_value(user_input, CONF_PORT, DEFAULT_BLE_PROXY_PORT),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_BLUETOOTH_ADDRESS,
                    default=user_value(user_input, CONF_BLUETOOTH_ADDRESS, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_BLUETOOTH_NAME,
                    default=user_value(user_input, CONF_BLUETOOTH_NAME, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_TIMEOUT,
                    default=user_value(user_input, CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=30,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=user_value(user_input, CONF_HOST, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_PORT,
                default=user_value(user_input, CONF_PORT, DEFAULT_PORT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TIMEOUT,
                default=user_value(user_input, CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def build_bluetooth_discovered_schema(
    discovered_meters: tuple[DiscoveredGrowBluetoothMeter, ...],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the form schema for selecting a discovered Bluetooth meter."""
    default_meter = (
        bluetooth_meter_key(discovered_meters[0]) if discovered_meters else ""
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_DISCOVERED_BLUETOOTH_METER,
                default=user_value(
                    user_input,
                    CONF_DISCOVERED_BLUETOOTH_METER,
                    default_meter,
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": bluetooth_meter_key(discovered_meter),
                            "label": discovered_meter.display_name,
                        }
                        for discovered_meter in discovered_meters
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            **bluetooth_meter_settings_schema(user_input),
        }
    )


def build_add_route_bluetooth_discovered_schema(
    discovered_meters: tuple[DiscoveredGrowBluetoothMeter, ...],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the form schema for selecting a discovered Bluetooth route."""
    default_meter = (
        bluetooth_meter_key(discovered_meters[0]) if discovered_meters else ""
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_DISCOVERED_BLUETOOTH_METER,
                default=user_value(
                    user_input,
                    CONF_DISCOVERED_BLUETOOTH_METER,
                    default_meter,
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": bluetooth_meter_key(discovered_meter),
                            "label": discovered_meter.display_name,
                        }
                        for discovered_meter in discovered_meters
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_SLAVE_ID,
                default=user_value(user_input, CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TIMEOUT,
                default=user_value(user_input, CONF_TIMEOUT, DEFAULT_BLUETOOTH_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=30,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def build_bluetooth_confirm_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Build the form schema for confirming one Bluetooth discovery."""
    return vol.Schema(bluetooth_meter_settings_schema(user_input))


def bluetooth_meter_settings_schema(
    user_input: dict[str, Any] | None,
) -> dict[vol.Marker, Any]:
    """Build shared Bluetooth meter settings fields."""
    return {
        vol.Required(
            CONF_SLAVE_ID,
            default=user_value(user_input, CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=247,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_TIMEOUT,
            default=user_value(user_input, CONF_TIMEOUT, DEFAULT_BLUETOOTH_TIMEOUT),
        ): NumberSelector(
            NumberSelectorConfig(
                min=10,
                max=30,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=user_value(
                user_input,
                CONF_SCAN_INTERVAL,
                DEFAULT_BLUETOOTH_SCAN_INTERVAL,
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }


def build_serial_scan_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Build the form schema for a serial GROW bus scan."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SERIAL_PORT,
                default=user_value(user_input, CONF_SERIAL_PORT, "COM1"),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_BAUDRATE,
                default=user_value(user_input, CONF_BAUDRATE, DEFAULT_BAUDRATE),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=300,
                    max=115200,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_BYTESIZE,
                default=user_value(user_input, CONF_BYTESIZE, DEFAULT_BYTESIZE),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=7,
                    max=8,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_PARITY,
                default=user_value(user_input, CONF_PARITY, DEFAULT_PARITY),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "N", "label": "None"},
                        {"value": "E", "label": "Even"},
                        {"value": "O", "label": "Odd"},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_STOPBITS,
                default=user_value(user_input, CONF_STOPBITS, DEFAULT_STOPBITS),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=2,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TIMEOUT,
                default=user_value(user_input, CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SLAVE_ID_START,
                default=user_value(user_input, CONF_SLAVE_ID_START, DEFAULT_SLAVE_ID),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SLAVE_ID_END,
                default=user_value(user_input, CONF_SLAVE_ID_END, DEFAULT_SLAVE_ID_END),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=user_value(
                    user_input, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def build_discovered_serial_schema(
    discovered_meters: tuple[DiscoveredGrowMeter, ...],
    *,
    scan_interval_default: int,
) -> vol.Schema:
    """Build the form schema for selecting one or more discovered serial meters."""
    default_meter_keys = [
        discovered_meter_key(discovered_meter) for discovered_meter in discovered_meters
    ]
    return vol.Schema(
        {
            vol.Required(
                CONF_DISCOVERED_METERS,
                default=default_meter_keys,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": discovered_meter_key(discovered_meter),
                            "label": discovered_meter.display_name,
                        }
                        for discovered_meter in discovered_meters
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=scan_interval_default,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def build_action_schema(
    action_options: list[dict[str, str]],
    default_action: str,
) -> vol.Schema:
    """Build the action chooser for the options flow."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ACTION,
                default=default_action,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=action_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def build_select_meter_schema(
    meter_options: list[dict[str, str]],
    default_meter_key: str,
) -> vol.Schema:
    """Build the meter chooser used before managing one shared-bus member."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SELECTED_METER,
                default=default_meter_key,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=meter_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def build_gateway_scan_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Build the form schema for a Modbus TCP gateway GROW bus scan."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=user_value(user_input, CONF_HOST, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_PORT,
                default=user_value(user_input, CONF_PORT, DEFAULT_PORT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TIMEOUT,
                default=user_value(user_input, CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SLAVE_ID_START,
                default=user_value(user_input, CONF_SLAVE_ID_START, DEFAULT_SLAVE_ID),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SLAVE_ID_END,
                default=user_value(
                    user_input,
                    CONF_SLAVE_ID_END,
                    DEFAULT_GATEWAY_SCAN_SLAVE_ID_END,
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=user_value(
                    user_input, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def build_discovered_gateway_schema(
    discovered_gateways: tuple[DiscoveredTcpGateway, ...],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the form schema for selecting one discovered TCP gateway."""
    default_gateway = (
        _discovered_gateway_key(discovered_gateways[0]) if discovered_gateways else ""
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_DISCOVERED_GATEWAY,
                default=user_value(
                    user_input,
                    CONF_DISCOVERED_GATEWAY,
                    default_gateway,
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": _discovered_gateway_key(discovered_gateway),
                            "label": discovered_gateway.display_name,
                        }
                        for discovered_gateway in discovered_gateways
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _discovered_gateway_key(discovered_gateway: DiscoveredTcpGateway) -> str:
    """Build a stable selector key for one discovered gateway."""
    return f"{discovered_gateway.host}:{discovered_gateway.port}"


def build_add_route_schema(
    supported_transports: tuple[TransportType, ...],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the first-step form for adding one additional route."""
    route_options = [
        {
            "value": transport.value,
            "label": TRANSPORT_LABELS[transport],
        }
        for transport in supported_transports
    ]
    default_transport = route_options[0]["value"]
    return vol.Schema(
        {
            vol.Required(
                CONF_TRANSPORT,
                default=user_value(user_input, CONF_TRANSPORT, default_transport),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=route_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def build_add_route_purpose_schema(
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the route-purpose chooser for helper-capable transports."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ROUTE_PURPOSE,
                default=user_value(
                    user_input, CONF_ROUTE_PURPOSE, ROUTE_PURPOSE_ONBOARDING
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": ROUTE_PURPOSE_ONBOARDING,
                            "label": "Provisioning/helper route only",
                        },
                        {
                            "value": ROUTE_PURPOSE_ACTIVE,
                            "label": "Use as active polling route",
                        },
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def build_add_route_connection_schema(
    transport: TransportType,
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the connection form for adding one route."""
    timeout_min = minimum_timeout_for_transport(transport)
    schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_SLAVE_ID,
            default=user_value(user_input, CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=247,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }

    if transport is TransportType.SERIAL:
        schema.update(
            {
                vol.Required(
                    CONF_SERIAL_PORT,
                    default=user_value(user_input, CONF_SERIAL_PORT, "COM1"),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_BAUDRATE,
                    default=user_value(user_input, CONF_BAUDRATE, DEFAULT_BAUDRATE),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=300,
                        max=115200,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_BYTESIZE,
                    default=user_value(user_input, CONF_BYTESIZE, DEFAULT_BYTESIZE),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=7,
                        max=8,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_PARITY,
                    default=user_value(user_input, CONF_PARITY, DEFAULT_PARITY),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "N", "label": "None"},
                            {"value": "E", "label": "Even"},
                            {"value": "O", "label": "Odd"},
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_STOPBITS,
                    default=user_value(user_input, CONF_STOPBITS, DEFAULT_STOPBITS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=2,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
    elif transport is TransportType.BLUETOOTH:
        schema.update(
            {
                vol.Required(
                    CONF_BLUETOOTH_ADDRESS,
                    default=user_value(user_input, CONF_BLUETOOTH_ADDRESS, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_BLUETOOTH_NAME,
                    default=user_value(user_input, CONF_BLUETOOTH_NAME, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }
        )
    elif transport is TransportType.BLUETOOTH_PROXY:
        schema.update(
            {
                vol.Required(
                    CONF_HOST,
                    default=user_value(user_input, CONF_HOST, DEFAULT_BLE_PROXY_HOST),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_PORT,
                    default=user_value(user_input, CONF_PORT, DEFAULT_BLE_PROXY_PORT),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_BLUETOOTH_ADDRESS,
                    default=user_value(user_input, CONF_BLUETOOTH_ADDRESS, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_BLUETOOTH_NAME,
                    default=user_value(user_input, CONF_BLUETOOTH_NAME, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }
        )
    else:
        schema.update(
            {
                vol.Required(
                    CONF_HOST,
                    default=user_value(user_input, CONF_HOST, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_PORT,
                    default=user_value(user_input, CONF_PORT, DEFAULT_PORT),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    schema[
        vol.Required(
            CONF_TIMEOUT,
            default=user_value(
                user_input,
                CONF_TIMEOUT,
                default_timeout_for_transport(transport),
            ),
        )
    ] = NumberSelector(
        NumberSelectorConfig(
            min=timeout_min,
            max=30,
            step=1,
            mode=NumberSelectorMode.BOX,
        )
    )
    return vol.Schema(schema)


def build_switch_route_schema(
    routes: tuple[ConfiguredRoute, ...],
    active_route_key: str | None,
) -> vol.Schema:
    """Build the route-switching selector for one single-meter entry."""
    default_route = active_route_key or build_route_key(routes[0])
    return vol.Schema(
        {
            vol.Required(
                CONF_SELECTED_ROUTE,
                default=default_route,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": build_route_key(route),
                            "label": describe_route(route),
                        }
                        for route in routes
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def build_update_polling_schema(default_scan_interval: int) -> vol.Schema:
    """Build the form for updating only the polling interval."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=default_scan_interval,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            )
        }
    )


def build_edit_serial_bus_schema(
    entry_data: dict[str, Any],
    entry_title: str,
    configured_meters: tuple[ConfiguredMeter, ...],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the form schema for editing a shared Modbus bus entry."""
    transport = TransportType(entry_data[CONF_TRANSPORT])
    schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_NAME,
            default=user_value(user_input, CONF_NAME, entry_title),
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(
            CONF_TIMEOUT,
            default=user_value(
                user_input,
                CONF_TIMEOUT,
                int(entry_data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=30,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=user_value(
                user_input,
                CONF_SCAN_INTERVAL,
                int(entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
    if transport is TransportType.SERIAL:
        schema.update(
            {
                vol.Required(
                    CONF_SERIAL_PORT,
                    default=user_value(
                        user_input,
                        CONF_SERIAL_PORT,
                        entry_data[CONF_SERIAL_PORT],
                    ),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_BAUDRATE,
                    default=user_value(
                        user_input,
                        CONF_BAUDRATE,
                        int(entry_data[CONF_BAUDRATE]),
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=300,
                        max=115200,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_BYTESIZE,
                    default=user_value(
                        user_input,
                        CONF_BYTESIZE,
                        int(entry_data[CONF_BYTESIZE]),
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=7,
                        max=8,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_PARITY,
                    default=user_value(
                        user_input, CONF_PARITY, entry_data[CONF_PARITY]
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "N", "label": "None"},
                            {"value": "E", "label": "Even"},
                            {"value": "O", "label": "Odd"},
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_STOPBITS,
                    default=user_value(
                        user_input,
                        CONF_STOPBITS,
                        int(entry_data[CONF_STOPBITS]),
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=2,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
    else:
        schema.update(
            {
                vol.Required(
                    CONF_HOST,
                    default=user_value(user_input, CONF_HOST, entry_data[CONF_HOST]),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_PORT,
                    default=user_value(
                        user_input,
                        CONF_PORT,
                        int(entry_data[CONF_PORT]),
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    for meter in configured_meters:
        schema[
            vol.Required(
                meter_slave_id_field(meter),
                default=user_value(
                    user_input,
                    meter_slave_id_field(meter),
                    get_bus_route_for_meter(
                        meter,
                        bus_entry_data=entry_data,
                    ).slave_id,
                ),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=247,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        )
    return vol.Schema(schema)


def build_update_connection_schema(
    entry_data: dict[str, Any],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the form schema for changing transport connection details."""
    transport = TransportType(entry_data[CONF_TRANSPORT])
    timeout_min = minimum_timeout_for_transport(transport)
    timeout_default = max(
        int(entry_data.get(CONF_TIMEOUT, default_timeout_for_transport(transport))),
        timeout_min,
    )
    base_schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_SLAVE_ID,
            default=user_value(
                user_input,
                CONF_SLAVE_ID,
                int(entry_data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)),
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=247,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_TIMEOUT,
            default=user_value(
                user_input,
                CONF_TIMEOUT,
                timeout_default,
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=timeout_min,
                max=30,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=user_value(
                user_input,
                CONF_SCAN_INTERVAL,
                int(entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }

    if transport is TransportType.SERIAL:
        serial_schema: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_SERIAL_PORT,
                default=user_value(
                    user_input,
                    CONF_SERIAL_PORT,
                    entry_data[CONF_SERIAL_PORT],
                ),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_BAUDRATE,
                default=user_value(
                    user_input,
                    CONF_BAUDRATE,
                    int(entry_data[CONF_BAUDRATE]),
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=300,
                    max=115200,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_BYTESIZE,
                default=user_value(
                    user_input,
                    CONF_BYTESIZE,
                    int(entry_data[CONF_BYTESIZE]),
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=7,
                    max=8,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_PARITY,
                default=user_value(
                    user_input,
                    CONF_PARITY,
                    entry_data[CONF_PARITY],
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "N", "label": "None"},
                        {"value": "E", "label": "Even"},
                        {"value": "O", "label": "Odd"},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_STOPBITS,
                default=user_value(
                    user_input,
                    CONF_STOPBITS,
                    int(entry_data[CONF_STOPBITS]),
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=2,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
        serial_schema.update(base_schema)
        return vol.Schema(serial_schema)

    if transport is TransportType.BLUETOOTH:
        bluetooth_schema: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_BLUETOOTH_ADDRESS,
                default=user_value(
                    user_input,
                    CONF_BLUETOOTH_ADDRESS,
                    entry_data[CONF_BLUETOOTH_ADDRESS],
                ),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_BLUETOOTH_NAME,
                default=user_value(
                    user_input,
                    CONF_BLUETOOTH_NAME,
                    entry_data.get(CONF_BLUETOOTH_NAME, ""),
                ),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        }
        bluetooth_schema.update(base_schema)
        return vol.Schema(bluetooth_schema)

    if transport is TransportType.BLUETOOTH_PROXY:
        bluetooth_proxy_schema: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_HOST,
                default=user_value(
                    user_input,
                    CONF_HOST,
                    entry_data[CONF_HOST],
                ),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_PORT,
                default=user_value(
                    user_input,
                    CONF_PORT,
                    int(entry_data[CONF_PORT]),
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_BLUETOOTH_ADDRESS,
                default=user_value(
                    user_input,
                    CONF_BLUETOOTH_ADDRESS,
                    entry_data[CONF_BLUETOOTH_ADDRESS],
                ),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_BLUETOOTH_NAME,
                default=user_value(
                    user_input,
                    CONF_BLUETOOTH_NAME,
                    entry_data.get(CONF_BLUETOOTH_NAME, ""),
                ),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        }
        bluetooth_proxy_schema.update(base_schema)
        return vol.Schema(bluetooth_proxy_schema)

    tcp_schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_HOST,
            default=user_value(user_input, CONF_HOST, entry_data[CONF_HOST]),
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Required(
            CONF_PORT,
            default=user_value(user_input, CONF_PORT, int(entry_data[CONF_PORT])),
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=65535,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
    tcp_schema.update(base_schema)
    return vol.Schema(tcp_schema)


def build_serial_bus_scan_schema(
    entry_data: dict[str, Any],
    user_input: dict[str, Any] | None,
) -> vol.Schema:
    """Build the rescan form for an existing serial bus."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SLAVE_ID_START,
                default=user_value(user_input, CONF_SLAVE_ID_START, DEFAULT_SLAVE_ID),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SLAVE_ID_END,
                default=user_value(user_input, CONF_SLAVE_ID_END, DEFAULT_SLAVE_ID_END),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=user_value(
                    user_input,
                    CONF_SCAN_INTERVAL,
                    int(entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )
