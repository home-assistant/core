"""Test the Grandstream Home utils module."""

from __future__ import annotations

import base64
from unittest.mock import patch

from homeassistant.components.grandstream_home.const import (
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
)
from homeassistant.components.grandstream_home.utils import (
    decrypt_password,
    encrypt_password,
    extract_mac_from_name,
    generate_unique_id,
    is_encrypted_password,
    mask_sensitive_data,
    validate_ip_address,
    validate_port,
)


# Test generate_unique_id function
def test_generate_unique_id_with_name() -> None:
    """Test generate_unique_id with device name."""
    result = generate_unique_id("Test Device", DEVICE_TYPE_GDS, "192.168.1.100", 80)
    assert result == "test_device"


def test_generate_unique_id_with_spaces() -> None:
    """Test generate_unique_id with spaces in name."""
    result = generate_unique_id("My GDS Device", DEVICE_TYPE_GDS, "192.168.1.100", 80)
    assert result == "my_gds_device"


def test_generate_unique_id_with_special_chars() -> None:
    """Test generate_unique_id with special characters."""
    result = generate_unique_id(
        "Test-Device.Name", DEVICE_TYPE_GDS, "192.168.1.100", 80
    )
    assert result == "test_device_name"


def test_generate_unique_id_without_name() -> None:
    """Test generate_unique_id without device name."""
    result = generate_unique_id("", DEVICE_TYPE_GDS, "192.168.1.100", 80)
    assert result == "gds_192_168_1_100_80"


def test_generate_unique_id_with_whitespace_name() -> None:
    """Test generate_unique_id with whitespace-only name."""
    result = generate_unique_id("   ", DEVICE_TYPE_GDS, "192.168.1.100", 80)
    assert result == "gds_192_168_1_100_80"


def test_generate_unique_id_gns_device() -> None:
    """Test generate_unique_id for GNS device."""
    result = generate_unique_id("", DEVICE_TYPE_GNS_NAS, "192.168.1.101", 5001)
    # Device type has underscore replaced, so GNS_NAS becomes gns
    assert result == "gns_192_168_1_101_5001"


def test_encrypt_password_empty() -> None:
    """Test encrypt_password with empty password."""
    assert encrypt_password("", "test_id") == ""


def test_encrypt_password_error() -> None:
    """Test encrypt_password with encryption error."""
    with patch("homeassistant.components.grandstream_home.utils.Fernet") as mock_fernet:
        mock_fernet.side_effect = ValueError("Encryption error")
        result = encrypt_password("password", "test_id")
        assert result == "password"  # Fallback to plaintext


def test_decrypt_password_empty() -> None:
    """Test decrypt_password with empty password."""
    assert decrypt_password("", "test_id") == ""


def test_decrypt_password_plaintext() -> None:
    """Test decrypt_password with plaintext (backward compatibility)."""
    assert decrypt_password("short", "test_id") == "short"


def test_decrypt_password_error() -> None:
    """Test decrypt_password with decryption error."""
    # Create a valid base64 string that's long enough but not valid Fernet
    fake_encrypted = base64.b64encode(b"X" * 60).decode()
    result = decrypt_password(fake_encrypted, "test_id")
    assert result == fake_encrypted  # Fallback to plaintext


def test_is_encrypted_password_short() -> None:
    """Test is_encrypted_password with short string."""
    assert is_encrypted_password("short") is False


def test_is_encrypted_password_invalid_base64() -> None:
    """Test is_encrypted_password with invalid base64."""
    assert is_encrypted_password("not@valid#base64!") is False


def test_decrypt_password_with_warning() -> None:
    """Test decrypt_password logs warning on error."""
    with patch(
        "homeassistant.components.grandstream_home.utils._LOGGER"
    ) as mock_logger:
        # Create invalid encrypted data that will trigger exception
        fake_encrypted = base64.b64encode(b"X" * 60).decode()
        result = decrypt_password(fake_encrypted, "test_id")

        # Should log warning
        assert mock_logger.warning.called
        assert result == fake_encrypted  # Fallback to plaintext


def test_encrypt_password_with_warning() -> None:
    """Test encrypt_password logs warning on error."""
    with patch(
        "homeassistant.components.grandstream_home.utils._get_encryption_key",
        side_effect=ValueError("Test error"),
    ):
        result = encrypt_password("test_password", "test_unique_id")
        # Should log warning and return original password as fallback
        assert result == "test_password"


def test_decrypt_password_success() -> None:
    """Test decrypt_password successful decryption."""
    # First encrypt a password
    original_password = "my_secret_password"
    encrypted = encrypt_password(original_password, "test_unique_id")

    # Then decrypt it
    decrypted = decrypt_password(encrypted, "test_unique_id")

    # Should match original
    assert decrypted == original_password


# Tests for extract_mac_from_name
def test_extract_mac_from_name_empty() -> None:
    """Test extract_mac_from_name with empty string."""
    assert extract_mac_from_name("") is None
    assert extract_mac_from_name(None) is None


def test_extract_mac_from_name_no_match() -> None:
    """Test extract_mac_from_name with no MAC pattern."""
    assert extract_mac_from_name("No MAC here") is None
    assert extract_mac_from_name("GDS_123") is None  # Too short


def test_extract_mac_from_name_with_underscore() -> None:
    """Test extract_mac_from_name with underscore pattern."""
    result = extract_mac_from_name("GDS_EC74D79753C5_")
    assert result == "ec:74:d7:97:53:c5"


def test_extract_mac_from_name_end_of_string() -> None:
    """Test extract_mac_from_name at end of string."""
    result = extract_mac_from_name("GDS_EC74D79753C5")
    assert result == "ec:74:d7:97:53:c5"


# Tests for validate_ip_address
def test_validate_ip_address_empty() -> None:
    """Test validate_ip_address with empty string."""
    assert validate_ip_address("") is False


def test_validate_ip_address_invalid() -> None:
    """Test validate_ip_address with invalid IP."""
    assert validate_ip_address("not-an-ip") is False
    assert validate_ip_address("999.999.999.999") is False


def test_validate_ip_address_with_whitespace() -> None:
    """Test validate_ip_address with whitespace."""
    assert validate_ip_address("  192.168.1.1  ") is True


# Tests for validate_port
def test_validate_port_invalid_value() -> None:
    """Test validate_port with invalid value."""
    assert validate_port("not-a-number") == (False, 0)
    assert validate_port(None) == (False, 0)


def test_validate_port_out_of_range() -> None:
    """Test validate_port with out of range values."""
    assert validate_port("0") == (False, 0)
    assert validate_port("65536") == (False, 65536)
    assert validate_port("-1") == (False, -1)


def test_encrypt_password_exception() -> None:
    """Test encrypt_password with exception."""
    with patch(
        "homeassistant.components.grandstream_home.utils._get_encryption_key"
    ) as mock_key:
        mock_key.side_effect = ValueError("Invalid key")
        result = encrypt_password("password", "test_id")
        assert result == "password"  # Fallback to plaintext


def test_decrypt_password_not_encrypted() -> None:
    """Test decrypt_password with plaintext."""
    assert decrypt_password("plaintext", "test_id") == "plaintext"


# Tests for mask_sensitive_data
def test_mask_sensitive_data_dict() -> None:
    """Test mask_sensitive_data with dict."""
    data = {
        "username": "admin",
        "password": "secret123",
        "token": "abc123",
        "nested": {"name": "value", "secret": "hidden"},
    }
    result = mask_sensitive_data(data)
    assert result["username"] == "admin"
    assert result["password"] == "***"
    assert result["token"] == "***"
    assert result["nested"]["name"] == "value"
    assert result["nested"]["secret"] == "***"


def test_mask_sensitive_data_list() -> None:
    """Test mask_sensitive_data with list."""
    data = [
        {"username": "admin", "password": "secret"},
        {"username": "user", "password": "pass"},
    ]
    result = mask_sensitive_data(data)
    assert result[0]["username"] == "admin"
    assert result[0]["password"] == "***"
    assert result[1]["username"] == "user"
    assert result[1]["password"] == "***"


def test_mask_sensitive_data_other() -> None:
    """Test mask_sensitive_data with non-dict/list."""
    assert mask_sensitive_data("plain string") == "plain string"
    assert mask_sensitive_data(123) == 123
    assert mask_sensitive_data(None) is None
