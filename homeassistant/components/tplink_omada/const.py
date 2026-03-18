"""Constants for the TP-Link Omada integration."""

from enum import StrEnum

DOMAIN = "tplink_omada"


class OmadaDeviceStatus(StrEnum):
    """Possible composite status values for Omada devices."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    PENDING = "pending"
    HEARTBEAT_MISSED = "heartbeat_missed"
    ISOLATED = "isolated"
    ADOPT_FAILED = "adopt_failed"
    MANAGED_EXTERNALLY = "managed_externally"
