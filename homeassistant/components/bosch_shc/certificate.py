"""Helper functions for Bosch SHC client certificate handling."""

from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from cryptography import x509

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util


class CertificateInfo(NamedTuple):
    """Parsed certificate info."""

    not_before: datetime
    not_after: datetime
    days_remaining: int


def parse_certificate(cert_path: str) -> CertificateInfo:
    """Parse a PEM certificate and return validity information.

    Raises HomeAssistantError if file missing or invalid.
    """
    path = Path(cert_path)
    if not path.is_file():
        raise HomeAssistantError(f"Certificate file missing: {cert_path}")

    data = path.read_bytes()
    try:
        cert = x509.load_pem_x509_certificate(data)
    except Exception as exc:  # pragma: no cover - defensive
        raise HomeAssistantError(f"Invalid certificate: {cert_path}") from exc

    now = dt_util.utcnow()
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    days_remaining = int((not_after - now).total_seconds() // 86400)
    return CertificateInfo(not_before, not_after, days_remaining)
