"""Helpers for Cert Expiry tests."""

from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def datetime_today():
    """Return the current day without time."""
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def past_timestamp(days):
    """Create timestamp object for requested days in the past."""
    delta = timedelta(days=days, minutes=1)
    return datetime_today() - delta


def future_timestamp(days):
    """Create timestamp object for requested days in future."""
    delta = timedelta(days=days, minutes=1)
    return datetime_today() + delta


def expired_certificate():
    """Create an expired certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test Expired Certificate")]
    )

    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(past_timestamp(100))
        .not_valid_after(past_timestamp(10))
        .sign(key, hashes.SHA256())
    )
