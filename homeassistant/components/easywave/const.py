"""Constants for the Easywave integration."""

from datetime import timedelta
from enum import IntFlag
from typing import Final

DOMAIN: Final = "easywave"

# ── Radio Frequency / Regulatory Compliance ─────────────────────────────────
# Home Assistant requires integrations to verify that RF hardware is permitted
# in the user's configured country. The RX11 USB Transceiver operates on
# 868 MHz (EU ISM band), which is only allowed in CEPT member countries.
FREQUENCY_868MHZ: Final = "868 MHz"

# ── USB Device Registry ──────────────────────────────────────────────────────
# Single source of truth for supported USB sticks.
# Adding a new device here is sufficient — config flow and discovery pick it up
# automatically. Also update the `usb` list in manifest.json.
#
# Key:   (VID, PID) as int
# Value: {"manufacturer": str, "product": str, "frequency": str}
USB_DEVICE_NAMES: Final[dict[tuple[int, int], dict[str, str]]] = {
    (0x155A, 0x1014): {
        "manufacturer": "ELDAT",
        "product": "RX11 USB Transceiver",
        "frequency": FREQUENCY_868MHZ,
    },
}

SUPPORTED_USB_IDS: Final = frozenset(USB_DEVICE_NAMES.keys())

# ── Coordinator Update Interval ──────────────────────────────────────────────
# Periodic polling interval for USB device reconnection attempts
DEVICE_SCAN_INTERVAL: Final = timedelta(seconds=30)


# ── Config Entry Keys ────────────────────────────────────────────────────────
CONF_DEVICE_PATH: Final = "device_path"
CONF_USB_VID: Final = "usb_vid"
CONF_USB_PID: Final = "usb_pid"
CONF_USB_SERIAL_NUMBER: Final = "usb_serial_number"
CONF_USB_MANUFACTURER: Final = "usb_manufacturer"
CONF_USB_PRODUCT: Final = "usb_product"

ALLOWED_COUNTRIES_868MHZ: Final = frozenset(
    {
        # EU Member States (CEPT)
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
        # CEPT Members (non-EU)
        "CH",
        "NO",
        "IS",
        "LI",
        # UK (post-Brexit)
        "GB",
        "UK",
    }
)

FREQUENCY_ALLOWED_COUNTRIES: Final = {
    FREQUENCY_868MHZ: ALLOWED_COUNTRIES_868MHZ,
}


def is_country_allowed_for_frequency(frequency: str, country_code: str | None) -> bool:
    """Check whether a country is permitted to operate on the given frequency.

    Args:
        frequency: The frequency band (e.g., FREQUENCY_868MHZ)
        country_code: ISO 3166-1 alpha-2 country code, or None if not configured

    Returns:
        True if country is allowed or unknown, False if explicitly disallowed.
    """
    # No country configured — cannot enforce
    if country_code is None:
        return True

    allowed = FREQUENCY_ALLOWED_COUNTRIES.get(frequency)
    if allowed is None:
        # Unknown frequency — conservative: allow
        return True

    return country_code.upper() in allowed


def get_frequency_for_pid(pid: int | None) -> str | None:
    """Get frequency band for a supported USB device PID."""
    if pid is None:
        return None
    for (_vid, device_pid), device_info in USB_DEVICE_NAMES.items():
        if device_pid == pid:
            return device_info["frequency"]
    return None


# Event fired for gateway/battery/button state changes (usable in automations).
EVENT_EASYWAVE: Final = f"{DOMAIN}_event"

# Device trigger event types
EVENT_TYPE_BUTTON_PRESS: Final = "button_press"
EVENT_TYPE_BUTTON_RELEASE: Final = "button_release"
EVENT_TYPE_BATTERY_LOW: Final = "battery_low"
EVENT_TYPE_BATTERY_NORMAL: Final = "battery_normal"
EVENT_TYPE_GATEWAY_CONNECTED: Final = "gateway_connected"
EVENT_TYPE_GATEWAY_DISCONNECTED: Final = "gateway_disconnected"

# ── Config Entry / Device Storage ────────────────────────────────────────────
CONF_DEVICE_TITLE: Final = "title"
CONF_DEVICE_DATA: Final = "data"
CONF_ENTRY_TYPE: Final = "entry_type"

SUBENTRY_DEVICE: Final = "device"
SUBENTRY_TYPE_TRANSMITTER: Final = "transmitter"
SUBENTRY_TYPE_NEO_SENSOR: Final = "neo_sensor"

ENTRY_TYPE_TRANSMITTER: Final = "transmitter"
ENTRY_TYPE_NEO_SENSOR: Final = "neo_sensor"

# ── Transmitter Configuration Keys ───────────────────────────────────────────
CONF_TRANSMITTER_SERIAL: Final = "transmitter_serial"

# ── EWneo Sensor Configuration Keys ────────────────────────────────────────────
CONF_SENSOR_SERIAL: Final = "sensor_serial"
CONF_SENSOR_CAPABILITIES: Final = "sensor_capabilities"

# ── Transmitter operating configuration ─────────────────────────────────────
CONF_OPERATING_TYPE: Final = "operating_type"
CONF_BUTTON_COUNT: Final = "button_count"
CONF_GROUPING_MODE: Final = "grouping_mode"
CONF_SWITCH_MODE: Final = "switch_mode"

# Grouping modes for 1-button transmitters (operating_type "1")
TRANSMITTER_GROUPING_GROUP: Final = "group"  # one shared "last button" entity

# Switch modes for 1-button transmitters (operating_type "1")
TRANSMITTER_SWITCH_IMPULSE: Final = (
    "impulse"  # state resets to "released" on button release
)
TRANSMITTER_SWITCH_PERMANENT: Final = "permanent"  # state persists until next press

BUTTON_A: Final = 0
BUTTON_B: Final = 1
BUTTON_C: Final = 2
BUTTON_D: Final = 3


class EasywaveTransmitterFeature(IntFlag):
    """Feature flags for transmitter last-button sensor trigger filtering."""

    BUTTON_A = 1
    BUTTON_B = 2
    BUTTON_C = 4
    BUTTON_D = 8
    BUTTON_RELEASE = 16


_BUTTON_FEATURE_BY_INDEX: Final = (
    EasywaveTransmitterFeature.BUTTON_A,
    EasywaveTransmitterFeature.BUTTON_B,
    EasywaveTransmitterFeature.BUTTON_C,
    EasywaveTransmitterFeature.BUTTON_D,
)


def transmitter_trigger_features(button_count: int, switch_mode: str) -> int:
    """Return supported trigger feature flags for a group-mode transmitter."""
    features = EasywaveTransmitterFeature(0)
    for index in range(min(button_count, 4)):
        features |= _BUTTON_FEATURE_BY_INDEX[index]
    if switch_mode == TRANSMITTER_SWITCH_IMPULSE:
        features |= EasywaveTransmitterFeature.BUTTON_RELEASE
    return features.value


class EasywaveGatewayFeature(IntFlag):
    """Feature flag for the RX11 gateway status sensor trigger filtering."""

    GATEWAY_STATUS = 32


# ── Learning Mode ────────────────────────────────────────────────────────────
LEARNING_TIMEOUT: Final = 30  # seconds
