"""Constants for the Diagnostics integration."""

from enum import StrEnum

DOMAIN = "diagnostics"

REDACTED = "**REDACTED**"


class DiagnosticsType(StrEnum):
    """Diagnostics types."""

    CONFIG_ENTRY = "config_entry"


class DiagnosticsSubType(StrEnum):
    """Diagnostics sub types."""

    DEVICE = "device"
