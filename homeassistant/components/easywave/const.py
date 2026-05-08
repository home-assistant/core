"""Constants for the Easywave integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "easywave"

# ── USB Device Registry ──────────────────────────────────────────────────────
# Single source of truth for supported USB sticks.
# Adding a new device here is sufficient — config flow and discovery pick it up
# automatically. Also update the `usb` list in manifest.json.
#
# Key:   (VID, PID) as int
# Value: {"manufacturer": str, "product": str}
USB_DEVICE_NAMES: Final[dict[tuple[int, int], dict[str, str]]] = {
    (0x155A, 0x1014): {
        "manufacturer": "ELDAT",
        "product": "RX11 USB Transceiver",
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

# ── Radio Frequency / Regulatory Compliance ─────────────────────────────────
# RX11 operates at 868 MHz (EU ISM band). Only permitted in CEPT countries.
FREQUENCY_868MHZ: Final = "868 MHz"

FREQUENCY_ALLOWED_COUNTRIES: Final = {
    FREQUENCY_868MHZ: frozenset(
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
    ),
}

# Legacy constant for backward compatibility
ALLOWED_COUNTRIES_868MHZ: Final = FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ]


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
    """Get frequency band for a USB device PID.

    RX11 USB Transceiver (0x1014) operates at 868 MHz.
    """
    if pid == 0x1014:
        return FREQUENCY_868MHZ
    return None


# Event fired for transmitter button presses (consumed by device_trigger).
EVENT_EASYWAVE: Final = f"{DOMAIN}_event"

# ── Config Entry / Subentry Types ────────────────────────────────────────────
CONF_ENTRY_TYPE: Final = "entry_type"

ENTRY_TYPE_RECEIVER: Final = "receiver"
ENTRY_TYPE_TRANSMITTER: Final = "transmitter"


# ── Receiver Configuration Keys ──────────────────────────────────────────────
CONF_GATEWAY_INDEX: Final = "gateway_index"
CONF_GATEWAY_SERIAL: Final = "gateway_serial"
CONF_RECEIVER_KIND: Final = "receiver_kind"

# Receiver kinds (operating modes)
RECEIVER_KIND_UNIVERSAL: Final = "universal_4button"

# ── Transmitter Configuration Keys ───────────────────────────────────────────
CONF_TRANSMITTER_SERIAL: Final = "transmitter_serial"
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

# ── Learning Mode ────────────────────────────────────────────────────────────
LEARNING_TIMEOUT: Final = 30  # seconds
