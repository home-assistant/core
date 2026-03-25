"""Common utility functions for Heiman Home integration."""

import hashlib
import logging
import re
from typing import Any

from .const import DOMAIN
from .heiman_device import HeimanDevice

_LOGGER = logging.getLogger(__name__)


def slugify_did(device_id: str) -> str:
    """Convert device ID to a safe slug for Home Assistant."""
    # Remove any characters that aren't alphanumeric, underscore, or hyphen
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(device_id)).lower()


def calc_group_id(home_id: str, home_name: str | None = None) -> str:
    """Calculate a group ID for home/family."""
    if home_name:
        return f"home_{home_id}_{slugify_did(home_name)}"
    return f"home_{home_id}"


def md5_hash(data: str) -> str:
    """Calculate MD5 hash of a string."""
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def device_model_to_model_type(model: str) -> str:
    """Extract model type from device model string."""
    # Remove any version numbers and special characters
    cleaned = re.sub(r"[^a-zA-Z]", "", str(model).split(".")[0])
    return cleaned.lower() if cleaned else "unknown"


def format_mac_address(mac: str) -> str:
    """Format MAC address to standard format."""
    if not mac:
        return "00:00:00:00:00:00"

    # Remove any separators
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac)

    # Format as XX:XX:XX:XX:XX:XX
    if len(cleaned) == 12:
        return ":".join([cleaned[i : i + 2] for i in range(0, 12, 2)]).upper()

    return mac


def safe_get_nested_value(data: dict[str, Any], keys: list, default: Any = None) -> Any:
    """Safely get a value from nested dictionary."""
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
        if data is None:
            return default
    return data


def parse_temperature(value: Any, default: float = 0.0) -> float:
    """Parse temperature value safely."""
    try:
        if value is None:
            return default
        return float(value)
    except ValueError, TypeError:
        _LOGGER.warning("Invalid temperature value: %s", value)
        return default


def parse_humidity(value: Any, default: int = 0) -> int:
    """Parse humidity value safely."""
    try:
        if value is None:
            return default
        # Ensure value is in range 0-100
        parsed = int(float(value))
        return max(0, min(100, parsed))
    except ValueError, TypeError:
        _LOGGER.warning("Invalid humidity value: %s", value)
        return default


def parse_bool(value: Any, default: bool = False) -> bool:
    """Parse boolean value safely."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on", "enabled")
    return default


def filter_none_values(data: dict) -> dict:
    """Remove None values from dictionary."""
    return {k: v for k, v in data.items() if v is not None}


def merge_dicts(*dicts: dict) -> dict:
    """Merge multiple dictionaries, with later ones overriding earlier ones."""
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result


def get_initialized_device(
    hass,
    entry_id: str,
    device_id: str,
    device_info: dict,
    cloud_client,
    i18n=None,
):
    """Get initialized HeimanDevice object from hass.data or create new one.

    This function reuses device objects that were pre-initialized in __init__.py
    to avoid re-creating them in each platform setup.

    Args:
        hass: HomeAssistant instance
        entry_id: Config entry ID
        device_id: Device ID
        device_info: Device info dict
        cloud_client: Cloud client instance
        i18n: Optional i18n instance

    Returns:
        HeimanDevice instance (may be uninitialized if not found in cache)
    """
    # Try to get from initialized devices cache
    initialized_devices = hass.data.get(DOMAIN, {}).get("heiman_devices", {})
    heiman_device = initialized_devices.get(entry_id, {}).get(device_id)

    if heiman_device:
        return heiman_device

    # Fallback: create new device object (should not happen normally)
    _LOGGER.warning(
        "No initialized device object found for %s, creating new one",
        device_id,
    )

    return HeimanDevice(
        hass=hass,
        device_info=device_info,
        cloud_client=cloud_client,
        entry_id=entry_id,
        i18n=i18n,
    )
