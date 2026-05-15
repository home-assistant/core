"""Public pyitach package API."""

from ._capabilities import (
    IR_OUTPUT_MODES,
    ItachIrCapability,
    async_get_ir_capability,
    enabled_ir_ports,
    enabled_ir_ports_with_fallback,
)
from ._client import DEFAULT_PORT, ItachClient
from ._discovery import (
    ItachDiscoveryBeacon,
    ItachDiscoveryListener,
    async_discover_once,
    normalize_host,
    normalize_uuid,
    parse_discovery_beacon,
)
from ._exceptions import (
    ItachBusyError,
    ItachCommandError,
    ItachConnectionError,
    ItachError,
    ItachIdentityError,
    ItachResponseError,
)
from ._identity import normalize_device_id
from ._protocol import (
    build_completeir_response_prefix,
    build_sendir_command,
    parse_device_line,
    parse_ir_response,
    parse_net_response,
)

__all__ = [
    "DEFAULT_PORT",
    "IR_OUTPUT_MODES",
    "ItachBusyError",
    "ItachClient",
    "ItachCommandError",
    "ItachConnectionError",
    "ItachDiscoveryBeacon",
    "ItachDiscoveryListener",
    "ItachError",
    "ItachIdentityError",
    "ItachIrCapability",
    "ItachResponseError",
    "async_discover_once",
    "async_get_ir_capability",
    "build_completeir_response_prefix",
    "build_sendir_command",
    "enabled_ir_ports",
    "enabled_ir_ports_with_fallback",
    "normalize_device_id",
    "normalize_host",
    "normalize_uuid",
    "parse_device_line",
    "parse_discovery_beacon",
    "parse_ir_response",
    "parse_net_response",
]
