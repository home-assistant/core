"""Helpers for Cert Expiry tests."""

from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

from homeassistant.components.cert_expiry.certs import HandshakeResult
from homeassistant.util import dt as dt_util


def static_datetime() -> datetime:
    """Build a datetime object for testing in the correct timezone."""
    return dt_util.as_utc(datetime(2020, 6, 12, 8, 0, 0))


def future_timestamp(days: int) -> datetime:
    """Create timestamp object for requested days in future."""
    delta = timedelta(days=days, minutes=1)
    return static_datetime() + delta


def certificate_expiring(
    not_valid_after: datetime,
    valid_for: timedelta = timedelta(days=3650),
) -> HandshakeResult:
    """Build a handshake result whose certificate expires at the given time."""
    # cryptography rejects datetimes of a different class than the one freezegun has
    # patched in, so rebuild them from timestamps.
    expires = datetime.fromtimestamp(not_valid_after.timestamp(), UTC)
    starts = datetime.fromtimestamp((not_valid_after - valid_for).timestamp(), UTC)
    # Fixed key and serial keep the fingerprint stable for snapshots.
    key = Ed25519PrivateKey.from_private_bytes(bytes(32))
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.com")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(0x1234ABCD)
        .not_valid_before(starts)
        .not_valid_after(expires)
        .sign(key, None)
    )
    return HandshakeResult(
        cert=cert,
        intermediates=[],
        tls_version="TLSv1.3",
        cipher_name="TLS_AES_256_GCM_SHA384",
        cipher_protocol="TLSv1.3",
    )


# cryptography caches the datetime class of the first datetime it sees. Building a
# certificate at import, before any test freezes time, caches the real class, which
# also accepts freezegun's subclass. This must stay an import-time side effect: a
# session-scoped autouse fixture runs too late for the first-collected test, since
# pytest_freezer's freeze_time marker inserts its own fixture ahead of every other
# fixture (including session-scoped ones) for the test it applies to.
certificate_expiring(datetime(2030, 1, 1, tzinfo=UTC))
