"""Helper functions."""

import re

from homeassistant.const import UnitOfInformation

# Strip a leading URL scheme (e.g. "https://" or "http://") from the host.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
# Everything from the first path/query/fragment delimiter is not part of host.
_HOST_TAIL_RE = re.compile(r"[/?#]")

# Attribute keys that must stay exactly as declared in strings.json's
# state_attributes for translation lookup to match (see format_attribute).
_UNFORMATTED_ATTRIBUTES = {"uuids"}


def sanitize_host(host: str) -> str:
    """Normalize user input to the bare hostname/IP[:port] the API expects.

    Lowercased so case differences don't create duplicate config entries.
    """
    host = host.strip()
    host = _SCHEME_RE.sub("", host)
    host = _HOST_TAIL_RE.split(host, maxsplit=1)[0]
    return host.strip().lower()


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


def format_attribute(attr: str) -> str:
    """Format attribute.

    Left as-is when a translation is declared for it in strings.json's
    ``state_attributes`` (currently only "uuids"): HA looks up that
    translation by the literal attribute key, so humanizing it here would
    make the lookup miss and silently fall back to the untranslated key.
    """
    if attr in _UNFORMATTED_ATTRIBUTES:
        return attr
    attr = attr.replace("_", " ")
    attr = attr.replace("-", " ")
    attr = attr.capitalize()
    # capitalize() lowercases a leading "zfs" to "Zfs"; replace both cases to get "ZFS".
    attr = attr.replace("Zfs", "ZFS")
    attr = attr.replace("zfs", "ZFS")
    attr = attr.replace(" gib", " GiB")
    attr = attr.replace("Cpu ", "CPU ")
    attr = attr.replace("Vcpu ", "vCPU ")
    attr = attr.replace("Vmware ", "VMware ")
    attr = attr.replace("Ip4 ", "IP4 ")
    return attr.replace("Ip6 ", "IP6 ")
