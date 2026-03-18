"""Tests for constants in the Easywave Core integration."""

from __future__ import annotations

from homeassistant.components.easywave.const import (
    ALLOWED_COUNTRIES_868MHZ,
    DOMAIN,
    EVENT_GATEWAY_CONNECTED,
    EVENT_GATEWAY_DISCONNECTED,
    EVENT_GATEWAY_STATUS_CHANGED,
    FREQUENCY_868MHZ,
    FREQUENCY_ALLOWED_COUNTRIES,
    SUPPORTED_USB_IDS,
    USB_DEVICE_NAMES,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)


def test_domain() -> None:
    """Test DOMAIN constant."""
    assert DOMAIN == "easywave"


def test_usb_device_names() -> None:
    """Test USB_DEVICE_NAMES constant."""
    assert isinstance(USB_DEVICE_NAMES, dict)
    assert (0x155A, 0x1014) in USB_DEVICE_NAMES

    device_info = USB_DEVICE_NAMES[(0x155A, 0x1014)]
    assert device_info["manufacturer"] == "ELDAT"
    assert device_info["product"] == "RX11 USB Transceiver"


def test_supported_usb_ids() -> None:
    """Test SUPPORTED_USB_IDS constant."""
    assert isinstance(SUPPORTED_USB_IDS, frozenset)
    assert (0x155A, 0x1014) in SUPPORTED_USB_IDS


def test_frequency_868mhz() -> None:
    """Test FREQUENCY_868MHZ constant."""
    assert FREQUENCY_868MHZ == "868 MHz"


def test_frequency_allowed_countries() -> None:
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


def test_allowed_countries_868mhz_legacy() -> None:
    """Test ALLOWED_COUNTRIES_868MHZ backward compatibility."""
    assert FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ] == ALLOWED_COUNTRIES_868MHZ
    assert "DE" in ALLOWED_COUNTRIES_868MHZ


def test_is_country_allowed_for_frequency_allowed() -> None:
    """Test is_country_allowed_for_frequency with allowed country."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "DE") is True
    assert (
        is_country_allowed_for_frequency(FREQUENCY_868MHZ, "de") is True
    )  # Case insensitive
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "FR") is True
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "GB") is True


def test_is_country_allowed_for_frequency_not_allowed() -> None:
    """Test is_country_allowed_for_frequency with disallowed country."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "US") is False
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "JP") is False
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "BR") is False


def test_is_country_allowed_for_frequency_none() -> None:
    """Test is_country_allowed_for_frequency with None country."""
    # No country configured — cannot enforce, so allow
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, None) is True


def test_is_country_allowed_for_frequency_unknown_frequency() -> None:
    """Test is_country_allowed_for_frequency with unknown frequency."""
    # Unknown frequency — conservative: allow
    assert is_country_allowed_for_frequency("unknown_freq", "US") is True


def test_get_frequency_for_pid_rx11() -> None:
    """Test get_frequency_for_pid for RX11."""
    assert get_frequency_for_pid(0x1014) == FREQUENCY_868MHZ


def test_get_frequency_for_pid_unknown() -> None:
    """Test get_frequency_for_pid with unknown PID."""
    assert get_frequency_for_pid(0x9999) is None
    assert get_frequency_for_pid(None) is None


def test_event_gateway_connected() -> None:
    """Test EVENT_GATEWAY_CONNECTED constant."""
    assert EVENT_GATEWAY_CONNECTED == "easywave_gateway_connected"


def test_event_gateway_disconnected() -> None:
    """Test EVENT_GATEWAY_DISCONNECTED constant."""
    assert EVENT_GATEWAY_DISCONNECTED == "easywave_gateway_disconnected"


def test_event_gateway_status_changed() -> None:
    """Test EVENT_GATEWAY_STATUS_CHANGED constant."""
    assert EVENT_GATEWAY_STATUS_CHANGED == "easywave_gateway_status_changed"
