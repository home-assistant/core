"""Helper functions."""

import ipaddress
import re

from homeassistant.const import UnitOfInformation

# Strip a leading URL scheme (e.g. "https://" or "http://") from the host.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
# Everything from the first path/query/fragment delimiter is not part of host.
_HOST_TAIL_RE = re.compile(r"[/?#]")


def sanitize_host(host: str) -> str:
    """Normalize user input to the bare hostname/IP[:port] the API expects.

    Lowercased so case differences don't create duplicate config entries.
    A bare IPv6 literal is bracketed (e.g. "::1" -> "[::1]") so it combines
    unambiguously with a scheme/port into a valid WebSocket URL.
    """
    host = host.strip()
    host = _SCHEME_RE.sub("", host)
    host = _HOST_TAIL_RE.split(host, maxsplit=1)[0]
    host = host.strip().lower()
    return _bracket_ipv6(host)


def _bracket_ipv6(host: str) -> str:
    """Bracket ``host`` if it is a bare (unbracketed) IPv6 literal."""
    try:
        ipaddress.IPv6Address(host)
    except ValueError:
        return host
    return f"[{host}]"


# (threshold_bytes, unit, precision) tiers; first match wins; _BASE_TIER_INDEX is the fallback tier.
_BINARY_TIERS = (
    (1024**5, UnitOfInformation.PEBIBYTES, 2),
    (1024**4, UnitOfInformation.TEBIBYTES, 2),
    (1024**3, UnitOfInformation.GIBIBYTES, None),
    (0, UnitOfInformation.MEBIBYTES, None),
)
_DECIMAL_TIERS = (
    (1000**5, UnitOfInformation.PETABYTES, 2),
    (1000**4, UnitOfInformation.TERABYTES, 2),
    (1000**3, UnitOfInformation.GIGABYTES, None),
    (0, UnitOfInformation.MEGABYTES, None),
)
_BASE_TIER_INDEX = 2  # GiB / GB


def scaled_data_unit(value: object, binary: bool) -> tuple[str, int | None]:
    """Pick a data-size display unit (and precision) by magnitude and base."""
    tiers = _BINARY_TIERS if binary else _DECIMAL_TIERS
    if not isinstance(value, (int, float)) or value <= 0:
        return tiers[_BASE_TIER_INDEX][1], None

    for threshold, unit, precision in tiers:
        if value >= threshold:
            return unit, precision

    return tiers[_BASE_TIER_INDEX][1], None
