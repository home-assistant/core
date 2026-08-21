"""Helper functions."""

import re
from typing import TYPE_CHECKING

from homeassistant.const import UnitOfInformation
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import TrueNASCoordinator

# Strip a leading URL scheme (e.g. "https://" or "http://") from the host.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
# Everything from the first path/query/fragment delimiter is not part of host.
_HOST_TAIL_RE = re.compile(r"[/?#]")


# ---------------------------
#   sanitize_host
# ---------------------------
def sanitize_host(host: str) -> str:
    """Normalize user input to the bare hostname/IP[:port] the API expects.

    Users frequently paste a full URL (for example
    ``https://nas.example.com/ui?tab=1``). The API layer requires a bare host,
    so strip any scheme as well as a trailing path, query or fragment here
    instead of erroring out, so the value just works. Hostnames (and DNS in
    general) are case-insensitive, so the result is also lowercased -- this
    keeps ``NAS.local`` and ``nas.local`` from being treated as two different
    hosts by the exact-string duplicate/rediscovery matching elsewhere.

    Lives here (rather than in ``config_flow``) so both ``config_flow`` and
    ``migration`` can depend on it without either importing the other.
    """
    host = host.strip()
    host = _SCHEME_RE.sub("", host)  # drop a leading scheme
    host = _HOST_TAIL_RE.split(host, maxsplit=1)[0]  # drop path/query/fragment
    return host.strip().lower()


# Data-size display tiers as (threshold_in_bytes, unit, precision). The first
# tier whose threshold the value reaches is used; a precision of ``None`` keeps
# the entity description's own precision. Index _BASE_TIER_INDEX (GiB/GB) is the
# base tier used for zero/unknown values. Binary tiers scale by 1024, decimal
# tiers by 1000.
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


# ---------------------------
#   scaled_data_unit
# ---------------------------
def scaled_data_unit(value: object, binary: bool) -> tuple[str, int | None]:
    """Pick a data-size display unit (and precision) by magnitude and base.

    Scales the displayed unit to the value relative to the configured base
    (binary GiB or decimal GB): >= 1 TiB/TB -> TiB/TB, >= 1 PiB/PB -> PiB/PB,
    and < 1 GiB/GB -> MiB/MB. A precision of ``None`` keeps the description's
    own precision.
    """
    tiers = _BINARY_TIERS if binary else _DECIMAL_TIERS
    if not isinstance(value, (int, float)) or value <= 0:
        return tiers[_BASE_TIER_INDEX][1], None

    for threshold, unit, precision in tiers:
        if value >= threshold:
            return unit, precision

    return tiers[_BASE_TIER_INDEX][1], None


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr: str) -> str:
    """Format attribute."""
    attr = attr.replace("_", " ")
    attr = attr.replace("-", " ")
    attr = attr.capitalize()
    # capitalize() only preserves "zfs" lowercase mid-string; a leading "zfs"
    # becomes "Zfs", so both cases need replacing to always yield "ZFS".
    attr = attr.replace("Zfs", "ZFS")
    attr = attr.replace("zfs", "ZFS")
    attr = attr.replace(" gib", " GiB")
    attr = attr.replace("Cpu ", "CPU ")
    attr = attr.replace("Vcpu ", "vCPU ")
    attr = attr.replace("Vmware ", "VMware ")
    attr = attr.replace("Ip4 ", "IP4 ")
    return attr.replace("Ip6 ", "IP6 ")


# ---------------------------
#   alert_action
# ---------------------------
async def alert_action(coordinator: TrueNASCoordinator, uuid: str, action: str) -> None:
    """Execute alert dismiss/restore action (shared helper)."""
    await coordinator.api.query(f"alert.{action}", [uuid])
    if coordinator.api.error:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="alert_action_failed",
            translation_placeholders={
                "action": action,
                "uuid": uuid,
                "host": coordinator.host,
                "error": str(coordinator.api.error),
            },
        )
    await coordinator.async_refresh()
