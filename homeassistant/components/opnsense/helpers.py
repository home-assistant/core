"""Helper methods for OPNsense."""

from collections.abc import MutableMapping
import ipaddress
import re
from typing import Any
from urllib.parse import urlparse


def dict_get(
    data: MutableMapping[str, Any], path: str, default: Any | None = None
) -> Any | None:
    """Parse the path to get the desired value out of the data."""
    path_list: list = re.split(r"\.", path, flags=re.IGNORECASE)
    result: Any | None = data

    for key in path_list:
        if isinstance(result, MutableMapping):
            dict_key: str | int = int(key) if key.isnumeric() else key
            if dict_key not in result:
                result = default
                break
            result = result[dict_key]
            continue

        if isinstance(result, list):
            if not key.isnumeric():
                result = default
                break
            index = int(key)
            if index < 0 or index >= len(result):
                result = default
                break
            result = result[index]
            continue

        result = default
        break

    return result


def is_private_ip(url: str) -> bool:
    """Check if the address in the given URL is a private IP address."""
    parsed_url = urlparse(url)
    addr = parsed_url.hostname
    if not addr:
        return False

    try:
        ip_obj = ipaddress.ip_address(addr)
    except ValueError:
        return False
    else:
        return ip_obj.is_private


def coerce_bool(value: Any) -> bool:
    """Normalize values that may represent booleans."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False
