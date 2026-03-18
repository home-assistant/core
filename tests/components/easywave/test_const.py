"""Tests for constants in the Easywave Core integration."""
from __future__ import annotations

from homeassistant.components.easywave.const import (
    DOMAIN,
    USB_DEVICE_NAMES,
    SUPPORTED_USB_IDS,
    FREQUENCY_868MHZ,
    FREQUENCY_ALLOWED_COUNTRIES,
    ALLOWED_COUNTRIES_868MHZ,
    is_country_allowed_for_frequency,
    get_frequency_for_pid,
    EVENT_GATEWAY_CONNECTED,
    EVENT_GATEWAY_DISCONNECTED,
    EVENT_GATEWAY_STATUS_CHANGED,
)


def test_domain():
    """Test DOMAIN constant."""
    assert DOMAIN == "easywave"


def test_usb_device_names():
    """Test USB_DEVICE_NAMES constant."""
    assert isinstance(USB_DEVICE_NAMES, dict)
    assert (0x155A, 0x1014) in USB_DEVICE_NAMES
    
    device_info = USB_DEVICE_NAMES[(0x155A, 0x1014)]
    assert device_info["manufacturer"] == "ELDAT"
    assert device_info["product"] == "RX11 USB Transceiver"


def test_supported_usb_ids():
    """Test SUPPORTED_USB_IDS constant."""
    assert isinstance(SUPPORTED_USB_IDS, frozenset)
    assert (0x155A, 0x1014) in SUPPORTED_USB_IDS


def test_frequency_868mhz():
    """Test FREQUENCY_868MHZ constant."""
    assert FREQUENCY_868MHZ == "868 MHz"


def test_frequency_allowed_countries():
    """Test FREQUENCY_ALLOWED_COUNTRIES constant."""
    assert isinstance(FREQUENCY_ALLOWED_COUNTRIES, dict)
    assert FREQUENCY_868MHZ in FREQUENCY_ALLOWED_COUNTRIES
    
    allowed = FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ]
    assert isinstance(allowed, frozenset)
    # Check some key countries
    assert "DE" in allowed  # Germany
    assert "FR" in allowed  # France
    assert "GB" in allowed  # UK
    assert "CH" in allowed  # Switzerland


def test_allowed_countries_868mhz_legacy():
    """Test ALLOWED_COUNTRIES_868MHZ backward compatibility."""
    assert ALLOWED_COUNTRIES_868MHZ == FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ]
    assert "DE" in ALLOWED_COUNTRIES_868MHZ


def test_is_country_allowed_for_frequency_allowed():
    """Test is_country_allowed_for_frequency with allowed country."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "DE") is True
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "de") is True  # Case insensitive
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "FR") is True
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "GB") is True


def test_is_country_allowed_for_frequency_not_allowed():
    """Test is_country_allowed_for_frequency with disallowed country."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "US") is False
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "JP") is False
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "BR") is False


def test_is_country_allowed_for_frequency_none():
    """Test is_country_allowed_for_frequency with None country."""
    # No country configured — cannot enforce, so allow
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, None) is True


def test_is_country_allowed_for_frequency_unknown_frequency():
    """Test is_country_allowed_for_frequency with unknown frequency."""
    # Unknown frequency — conservative: allow
    assert is_country_allowed_for_frequency("unknown_freq", "US") is True


def test_get_frequency_for_pid_rx11():
    """Test get_frequency_for_pid for RX11."""
    assert get_frequency_for_pid(0x1014) == FREQUENCY_868MHZ


def test_get_frequency_for_pid_unknown():
    """Test get_frequency_for_pid with unknown PID."""
    assert get_frequency_for_pid(0x9999) is None
    assert get_frequency_for_pid(None) is None


def test_event_gateway_connected():
    """Test EVENT_GATEWAY_CONNECTED constant."""
    assert EVENT_GATEWAY_CONNECTED == "easywave_gateway_connected"


def test_event_gateway_disconnected():
    """Test EVENT_GATEWAY_DISCONNECTED constant."""
    assert EVENT_GATEWAY_DISCONNECTED == "easywave_gateway_disconnected"


def test_event_gateway_status_changed():
    """Test EVENT_GATEWAY_STATUS_CHANGED constant."""
    assert EVENT_GATEWAY_STATUS_CHANGED == "easywave_gateway_status_changed"

