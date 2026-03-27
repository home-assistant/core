"""Utility functions for Grandstream Home integration."""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import logging
import re
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .const import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


def extract_mac_from_name(name: str | None) -> str | None:
    """Extract MAC address from device name.

    Device names often contain MAC address in format like:
    - GDS_EC74D79753C5
    - GNS_xxx_EC74D79753C5

    Args:
        name: Device name to extract MAC from

    Returns:
        Formatted MAC address (e.g., "ec:74:d7:97:53:c5") or None

    """
    if not name:
        return None

    # Look for 12 consecutive hex characters (MAC without colons)
    match = re.search(r"([0-9A-Fa-f]{12})(?:_|$)", name)
    if match:
        mac_hex = match.group(1).upper()
        # Format as xx:xx:xx:xx:xx:xx
        formatted_mac = ":".join(mac_hex[i : i + 2] for i in range(0, 12, 2)).lower()
        _LOGGER.debug("Extracted MAC %s from name %s", formatted_mac, name)
        return formatted_mac

    return None


def validate_ip_address(ip_str: str) -> bool:
    """Validate IP address format.

    Args:
        ip_str: IP address string to validate

    Returns:
        bool: True if valid, False otherwise

    """
    try:
        ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False
    else:
        return True


def validate_port(port_value: str | None) -> tuple[bool, int]:
    """Validate port number.

    Args:
        port_value: Port value to validate

    Returns:
        tuple: (is_valid, port_number)

    """
    if port_value is None:
        return False, 0
    try:
        port = int(port_value)
    except ValueError, TypeError:
        return False, 0
    else:
        return (1 <= port <= 65535), port


def _get_encryption_key(unique_id: str) -> bytes:
    """Generate a consistent encryption key based on unique_id."""
    # Use unique_id + a fixed salt to generate key
    salt = hashlib.sha256(f"grandstream_home_{unique_id}_salt_2026".encode()).digest()
    key_material = (unique_id + "grandstream_home").encode() + salt
    key = hashlib.sha256(key_material).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_password(password: str, unique_id: str) -> str:
    """Encrypt password using Fernet encryption.

    Args:
        password: Plain text password
        unique_id: Device unique ID for key generation

    Returns:
        str: Encrypted password (base64 encoded)

    """
    if not password:
        return ""

    try:
        key = _get_encryption_key(unique_id)
        f = Fernet(key)
        encrypted = f.encrypt(password.encode())
        return base64.b64encode(encrypted).decode()
    except (ValueError, TypeError, OSError) as e:
        _LOGGER.warning("Failed to encrypt password: %s", e)
        return password  # Fallback to plaintext


def decrypt_password(encrypted_password: str, unique_id: str) -> str:
    """Decrypt password using Fernet encryption.

    Args:
        encrypted_password: Encrypted password (base64 encoded)
        unique_id: Device unique ID for key generation

    Returns:
        str: Plain text password

    """
    if not encrypted_password:
        return ""

    # Check if it looks like encrypted data (base64 + reasonable length)
    if not is_encrypted_password(encrypted_password):
        return encrypted_password  # Assume plaintext for backward compatibility

    try:
        key = _get_encryption_key(unique_id)
        f = Fernet(key)
        encrypted_bytes = base64.b64decode(encrypted_password.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except (ValueError, TypeError, OSError, binascii.Error, InvalidToken) as e:
        _LOGGER.warning("Failed to decrypt password, using as plaintext: %s", e)
        return encrypted_password  # Fallback to plaintext


def is_encrypted_password(password: str) -> bool:
    """Check if password appears to be encrypted.

    Args:
        password: Password string to check

    Returns:
        bool: True if password appears encrypted

    """
    try:
        # Try to decode as base64, if successful it might be encrypted
        base64.b64decode(password.encode())
        return len(password) > 50  # Encrypted passwords are typically longer
    except ValueError, TypeError, binascii.Error:
        return False


# Sensitive fields that should be masked in logs
SENSITIVE_FIELDS = {
    "password",
    "access_token",
    "token",
    "session_id",
    "secret",
    "key",
    "credential",
    "sid",
    "dwt",
    "jwt",
}


def mask_sensitive_data(data: Any) -> Any:
    """Mask sensitive fields in data for safe logging.

    Args:
        data: Data to mask (dict, list, or other)

    Returns:
        Data with sensitive fields masked as ***

    """
    if isinstance(data, dict):
        return {
            k: "***"
            if k.lower() in SENSITIVE_FIELDS or k in SENSITIVE_FIELDS
            else mask_sensitive_data(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    return data


def generate_unique_id(
    device_name: str, device_type: str, host: str, port: int = DEFAULT_PORT
) -> str:
    """Generate device unique ID.

    Prioritize using device name as the basis for unique ID. If device name is empty, use IP address and port.

    Args:
        device_name: Device name
        device_type: Device type (GDS, GNS_NAS)
        host: Device IP address
        port: Device port

    Returns:
        str: Formatted unique ID

    """
    # Clean device name, remove special characters
    if device_name and device_name.strip():
        # Use device name as the basis for unique ID
        clean_name = (
            device_name.strip().replace(" ", "_").replace("-", "_").replace(".", "_")
        )
        unique_id = f"{clean_name}"
    else:
        # If no device name, use IP address and port
        clean_host = host.replace(".", "_").replace(":", "_")
        unique_id = f"{device_type}_{clean_host}_{port}"

    # Ensure unique ID contains no special characters and convert to lowercase
    return unique_id.replace(" ", "_").replace("-", "_").lower()


__all__ = [
    "decrypt_password",
    "encrypt_password",
    "extract_mac_from_name",
    "generate_unique_id",
    "mask_sensitive_data",
    "validate_ip_address",
    "validate_port",
]
