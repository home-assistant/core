"""Constants for the HEMS echonet lite integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "echonet_lite"
CONF_INTERFACE = "interface"
CONF_POLL_INTERVAL = "poll_interval"
CONF_ENABLE_EXPERIMENTAL = "enable_experimental"
DEFAULT_INTERFACE = "0.0.0.0"
DEFAULT_POLL_INTERVAL = 60
MIN_POLL_INTERVAL = 10
MAX_POLL_INTERVAL = 3600
UNIQUE_ID = "echonet_lite_singleton"
ISSUE_RUNTIME_CLIENT_ERROR = "runtime_client_error"
ISSUE_RUNTIME_INACTIVE = "runtime_inactive"
RUNTIME_MONITOR_INTERVAL = timedelta(minutes=1)
RUNTIME_MONITOR_MAX_SILENCE = timedelta(minutes=5)
DISCOVERY_INTERVAL = 60.0 * 60.0  # 1 hour

# Device identification EPCs
EPC_MANUFACTURER_CODE = 0x8A
EPC_PRODUCT_CODE = 0x8C
EPC_SERIAL_NUMBER = 0x8D

# Property map EPCs
EPC_INF_PROPERTY_MAP = 0x9D
EPC_SET_PROPERTY_MAP = 0x9E
EPC_GET_PROPERTY_MAP = 0x9F

# Stable (non-experimental) device class codes
# These device classes have been verified with real hardware.
# Other device classes are considered experimental.
STABLE_CLASS_CODES: frozenset[int] = frozenset(
    {
        0x0130,  # Home air conditioner
        0x0135,  # Air cleaner
        0x0279,  # Fuel cell (residential solar power generation)
        0x027D,  # In-house power generation (storage battery)
        0x05FF,  # Controller
    }
)


__all__ = [
    "CONF_ENABLE_EXPERIMENTAL",
    "CONF_INTERFACE",
    "CONF_POLL_INTERVAL",
    "DEFAULT_INTERFACE",
    "DEFAULT_POLL_INTERVAL",
    "DISCOVERY_INTERVAL",
    "DOMAIN",
    "EPC_GET_PROPERTY_MAP",
    "EPC_INF_PROPERTY_MAP",
    "EPC_MANUFACTURER_CODE",
    "EPC_PRODUCT_CODE",
    "EPC_SERIAL_NUMBER",
    "EPC_SET_PROPERTY_MAP",
    "ISSUE_RUNTIME_CLIENT_ERROR",
    "ISSUE_RUNTIME_INACTIVE",
    "MAX_POLL_INTERVAL",
    "MIN_POLL_INTERVAL",
    "RUNTIME_MONITOR_INTERVAL",
    "RUNTIME_MONITOR_MAX_SILENCE",
    "STABLE_CLASS_CODES",
    "UNIQUE_ID",
]
