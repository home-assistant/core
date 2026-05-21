"""Identity helpers for the Elke27 integration."""

from .const import MANUFACTURER_NUMBER


def derive_client_id(entry_id: str) -> str:
    """Return the Elk client ID for this Home Assistant config entry."""
    return "".join(ch for ch in entry_id if ch.isalnum()).lower()


def build_client_identity(client_id: str) -> dict[str, str]:
    """Return the client identity mapping for provisioning and session setup."""
    return {
        "mn": str(MANUFACTURER_NUMBER),
        "sn": client_id,
    }
